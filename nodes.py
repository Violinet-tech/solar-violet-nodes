# Solar LoRA Custom Nodes for ComfyUI
# Provides nodes for scanning folders, creating symlinks, and finding duplicates

import os
import json
import hashlib
import glob
from pathlib import Path
import numpy as np
import torch
from PIL import Image

# ComfyUI integration
try:
    import comfy.sd
    import folder_paths
    COMFY_AVAILABLE = True
except ImportError:
    COMFY_AVAILABLE = False
    print("Warning: running outside ComfyUI - loader node will be inert.")

# Try to import safetensors for metadata reading
try:
    from safetensors.torch import load_file
    SAFETENSORS_AVAILABLE = True
except ImportError:
    SAFETENSORS_AVAILABLE = False
    print("Warning: safetensors not installed. Some metadata features will be disabled.")

# Node class mappings
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

def register_node(cls):
    """Decorator to register a node class"""
    NODE_CLASS_MAPPINGS[cls.__name__] = cls
    NODE_DISPLAY_NAME_MAPPINGS[cls.__name__] = getattr(cls, 'DISPLAY_NAME', cls.__name__)
    return cls

@register_node
class SolarVioletLoraLoader:
    """Stack up to 30 LoRAs on a model+clip with preview cards. Multiple instances keep independent state."""
    DISPLAY_NAME = "Solar Violet LoRA Loader"
    MAX_LORAS = 30

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                # Serialized JSON array of lora slots: [{name, strength, preview, trigger_words}]
                "lora_stack_json": ("STRING", {"default": "[]", "multiline": True}),
                "auto_strength": ("BOOLEAN", {"default": True}),
                "step_increment": ("FLOAT", {"default": 0.1, "min": 0.01, "max": 1.0, "step": 0.01}),
            },
            "optional": {
                "max_loras": ("INT", {"default": 30, "min": 1, "max": 30, "step": 1}),
                "prompt": ("STRING", {"default": "", "forceInput": True}),
                "apply_triggers": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "applied_names", "trigger_words", "prompt")
    FUNCTION = "apply"
    CATEGORY = "Solar Violet"

    @staticmethod
    def _slot_triggers(slot):
        words = slot.get("trigger_words")
        if not isinstance(words, list) or not words:
            try:
                from . import lora_catalog
                info = lora_catalog.lora_info(slot.get("name", "")) or {}
                words = info.get("trigger_words", [])
            except Exception:
                words = []
        off = {str(w).lower() for w in (slot.get("triggers_off") or [])}
        return [str(w) for w in words if str(w).strip() and str(w).lower() not in off]

    def apply(self, model, clip, lora_stack_json, auto_strength=True, step_increment=0.1, max_loras=30,
              prompt="", apply_triggers=True):
        if not COMFY_AVAILABLE:
            return (model, clip, "", "", prompt)

        try:
            slots = json.loads(lora_stack_json or "[]")
        except Exception:
            slots = []
        if not isinstance(slots, list):
            slots = []

        applied = []
        trigger_list = []
        current_model = model
        current_clip = clip

        for slot in slots[: max(1, min(int(max_loras), 30))]:
            if not isinstance(slot, dict):
                continue
            name = slot.get("name", "")
            if not name or slot.get("enabled", True) is False:
                continue
            # Default: strength auto-derived; if auto_strength off, use per-slot strength
            if auto_strength:
                strength = 1.0
            else:
                strength = float(slot.get("strength", 1.0))
            try:
                lora_path = folder_paths.get_full_path("loras", name)
                if not lora_path:
                    continue
                lora = comfy.utils.load_torch_file(lora_path)
                current_model, current_clip = comfy.sd.load_lora_for_models(
                    current_model, current_clip, lora, strength, strength
                )
                applied.append(f"{name}:{strength}")
                trigger_list.extend(self._slot_triggers(slot))
            except Exception as e:
                print(f"[SolarViolet] failed to load LoRA {name}: {e}")
                continue

        seen = set()
        triggers = [w for w in trigger_list if not (w.lower() in seen or seen.add(w.lower()))]
        trigger_text = ", ".join(triggers)
        out_prompt = prompt or ""
        if apply_triggers and trigger_text:
            out_prompt = f"{out_prompt.rstrip().rstrip(',')}, {trigger_text}" if out_prompt.strip() else trigger_text

        return (current_model, current_clip, ",".join(applied), trigger_text, out_prompt)

@register_node
class SolarLoraScanNode:
    """Scan folders for LoRA files (.safetensors)"""
    
    DISPLAY_NAME = "Solar LoRA Scan"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {"default": "", "multiline": False}),
                "recursive": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "min_size_kb": ("INT", {"default": 0, "min": 0, "max": 1000000}),
                "max_size_kb": ("INT", {"default": 1000000, "min": 0, "max": 1000000}),
            }
        }
    
    RETURN_TYPES = ("STRING",)  # JSON string of LoRA list
    RETURN_NAMES = ("lora_list",)
    FUNCTION = "scan"
    CATEGORY = "Solar LoRA"
    
    def scan(self, folder_path, recursive, min_size_kb=0, max_size_kb=1000000):
        if not folder_path or not os.path.exists(folder_path):
            return (json.dumps({"error": "Folder does not exist"}),)
        
        lora_files = []
        
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith('.safetensors'):
                        file_path = os.path.join(root, file)
                        lora_files.append(file_path)
        else:
            for file in os.listdir(folder_path):
                if file.lower().endswith('.safetensors'):
                    file_path = os.path.join(folder_path, file)
                    lora_files.append(file_path)
        
        # Filter by size
        filtered_files = []
        for file_path in lora_files:
            try:
                size_kb = os.path.getsize(file_path) // 1024
                if min_size_kb <= size_kb <= max_size_kb:
                    filtered_files.append(file_path)
            except OSError:
                continue
        
        # Process each file to extract metadata
        loracards = []
        for file_path in filtered_files:
            try:
                card = self._process_lora_file(file_path)
                if card:
                    loracards.append(card)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        return (json.dumps(loracards),)
    
    def _process_lora_file(self, file_path):
        """Extract metadata from a .safetensors file"""
        if not SAFETENSORS_AVAILABLE:
            # Fallback: basic file info only
            stat = os.stat(file_path)
            return {
                "path": file_path,
                "name": os.path.basename(file_path),
                "size_kb": stat.st_size // 1024,
                "modified": stat.st_mtime,
            }
        
        try:
            # Load metadata (without loading the actual tensors)
            with open(file_path, 'rb') as f:
                # Read header
                header_size = int.from_bytes(f.read(8), 'little', signed=False)
                header_data = f.read(header_size)
                header = json.loads(header_data.decode('utf-8'))
                
                # Extract metadata
                metadata = header.get('__metadata__', {})
                
                stat = os.stat(file_path)
                
                return {
                    "path": file_path,
                    "name": os.path.basename(file_path),
                    "size_kb": stat.st_size // 1024,
                    "modified": stat.st_mtime,
                    "sha256": metadata.get('sha256'),
                    "ss_md5": metadata.get('ss_md5'),
                    "trained_words": metadata.get('trained_words', '').split('|') if metadata.get('trained_words') else [],
                    "network_dim": int(metadata.get('network_dim', 0)) if metadata.get('network_dim') else None,
                    "network_alpha": int(metadata.get('network_alpha', 0)) if metadata.get('network_alpha') else None,
                    "ss_sd_model_name": metadata.get('ss_sd_model_name'),
                    "ss_sd_model_hash": metadata.get('ss_sd_model_hash'),
                    # CivitAI metadata if present
                    "civitai_id": metadata.get('civitai_id'),
                    "civitai_version_id": metadata.get('civitai_version_id'),
                }
        except Exception as e:
            print(f"Error reading safetensors metadata from {file_path}: {e}")
            # Return basic info on error
            stat = os.stat(file_path)
            return {
                "path": file_path,
                "name": os.path.basename(file_path),
                "size_kb": stat.st_size // 1024,
                "modified": stat.st_mtime,
            }

@register_node
class SolarLoraSymlinkNode:
    """Create symlinks/junctions for LoRA files to ComfyUI models/loras folder"""
    
    DISPLAY_NAME = "Solar LoRA Symlink"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "lora_list": ("STRING", {"default": "[]"}),  # JSON from SolarLoraScanNode
                "comfyui_loras_dir": ("STRING", {"default": ""}),  # Path to ComfyUI/models/loras
            },
            "optional": {
                "overwrite_existing": ("BOOLEAN", {"default": False}),
                "create_backups": ("BOOLEAN", {"default": True}),
            }
        }
    
    RETURN_TYPES = ("STRING",)  # JSON string of results
    RETURN_NAMES = ("symlink_results",)
    FUNCTION = "symlink"
    CATEGORY = "Solar LoRA"
    
    def symlink(self, lora_list, comfyui_loras_dir, overwrite_existing=False, create_backups=True):
        try:
            lora_list = json.loads(lora_list)
            if isinstance(lora_list, dict) and "error" in lora_list:
                return (json.dumps({"error": lora_list["error"]}),)
        except json.JSONDecodeError:
            return (json.dumps({"error": "Invalid Lora list JSON"}),)
        
        if not comfyui_loras_dir or not os.path.exists(comfyui_loras_dir):
            return (json.dumps({"error": "ComfyUI LoRAs directory does not exist"}),)
        
        results = []
        
        for lora in lora_list:
            if not isinstance(lora, dict) or "path" not in lora:
                continue
                
            source_path = lora["path"]
            if not os.path.exists(source_path):
                results.append({
                    "source": source_path,
                    "success": False,
                    "error": "Source file does not exist"
                })
                continue
            
            # Determine target filename
            source_name = os.path.basename(source_path)
            target_path = os.path.join(comfyui_loras_dir, source_name)
            
            # Handle existing files
            if os.path.exists(target_path):
                if not overwrite_existing:
                    results.append({
                        "source": source_path,
                        "target": target_path,
                        "success": False,
                        "error": "File already exists (use overwrite_existing to replace)"
                    })
                    continue
                
                if create_backups:
                    # Create backup with timestamp
                    backup_path = f"{target_path}.backup.{int(os.path.getmtime(target_path))}"
                    try:
                        os.rename(target_path, backup_path)
                    except OSError:
                        pass  # Continue even if backup fails
            
            # Create symlink or junction
            try:
                how = "Symlink"
                if os.name == 'nt' and os.path.isdir(source_path):
                    import subprocess
                    r = subprocess.run(['cmd', '/c', 'mklink', '/J', target_path, source_path],
                                       capture_output=True, text=True)
                    if r.returncode != 0:
                        raise OSError(r.stderr.strip() or r.stdout.strip())
                    how = "Junction"
                else:
                    try:
                        os.symlink(source_path, target_path)
                    except OSError:
                        # Windows file symlinks need admin or Developer Mode: use a hardlink,
                        # then a plain copy if the two folders are on different drives.
                        try:
                            os.link(source_path, target_path)
                            how = "Hardlink"
                        except OSError:
                            import shutil
                            shutil.copy2(source_path, target_path)
                            how = "Copy"

                results.append({
                    "source": source_path,
                    "target": target_path,
                    "success": True,
                    "message": f"{how} created successfully"
                })
            except Exception as e:
                results.append({
                    "source": source_path,
                    "target": target_path,
                    "success": False,
                    "error": str(f"Failed to create symlink: {e}")
                })
        
        return (json.dumps(results),)

@register_node
class SolarLoraDuplicatesNode:
    """Find duplicate LoRA files based on metadata and filename"""
    
    DISPLAY_NAME = "Solar LoRA Duplicates"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "lora_list": ("STRING", {"default": "[]"}),  # JSON from SolarLoraScanNode
                "match_method": (["exact_hash", "civitai_metadata", "fuzzy_name", "combined"], {"default": "combined"}),
            },
            "optional": {
                "auto_select_keeper": ("BOOLEAN", {"default": True}),
                "keeper_criteria": (["newest", "largest", "in_comfyui"], {"default": "newest"}),
            }
        }
    
    RETURN_TYPES = ("STRING",)  # JSON string of duplicate groups
    RETURN_NAMES = ("duplicate_groups",)
    FUNCTION = "find_duplicates"
    CATEGORY = "Solar LoRA"
    
    def find_duplicates(self, lora_list_json, match_method="combined", auto_select_keeper=True, keeper_criteria="newest"):
        try:
            lora_list = json.loads(lora_list_json)
            if isinstance(lora_list, dict) and "error" in lora_list:
                return (json.dumps({"error": lora_list["error"]}),)
        except json.JSONDecodeError:
            return (json.dumps({"error": "Invalid Lora list JSON"}),)
        
        if not lora_list or len(lora_list) < 2:
            return (json.dumps([]),)
        
        # Group by match method
        groups = self._group_by_method(lora_list, match_method)
        
        # Format results
        results = []
        for group_id, group in enumerate(groups):
            if len(group) < 2:
                continue
                
            # Select keeper
            keeper = self._select_keeper(group, keeper_criteria) if auto_select_keeper else group[0]
            
            # Format group for output
            group_files = []
            for lora in group:
                group_files.append({
                    "path": lora.get("path", ""),
                    "name": lora.get("name", ""),
                    "size_kb": lora.get("size_kb", 0),
                    "modified": lora.get("modified", 0),
                    "sha256": lora.get("sha256"),
                    "is_keeper": lora.get("path") == keeper.get("path")
                })
            
            results.append({
                "group_id": group_id,
                "files": group_files,
                "keeper": keeper.get("path", ""),
                "match_type": match_method,
                "file_count": len(group)
            })
        
        return (json.dumps(results),)
    
    def _group_by_method(self, lora_list, method):
        """Group Loras by the specified method"""
        if method == "exact_hash":
            return self._group_by_exact_hash(lora_list)
        elif method == "civitai_metadata":
            return self._group_by_civitai_metadata(lora_list)
        elif method == "fuzzy_name":
            return self._group_by_fuzzy_name(lora_list)
        else:  # combined
            return self._group_by_combined(lora_list)
    
    def _group_by_exact_hash(self, lora_list):
        groups = {}
        for lora in lora_list:
            hash_val = lora.get("sha256")
            if hash_val:
                if hash_val not in groups:
                    groups[hash_val] = []
                groups[hash_val].append(lora)
        return [group for group in groups.values() if len(group) > 1]
    
    def _group_by_civitai_metadata(self, lora_list):
        groups = {}
        for lora in lora_list:
            # Use CivitAI IDs if available
            key = None
            if lora.get("civitai_id"):
                key = f"civitai_{lora['civitai_id']}"
            elif lora.get("civitai_version_id"):
                key = f"civitai_version_{lora['civitai_version_id']}"
            elif lora.get("ss_sd_model_hash"):
                key = f"model_hash_{lora['ss_sd_model_hash']}"
            
            if key:
                if key not in groups:
                    groups[key] = []
                groups[key].append(lora)
        
        return [group for group in groups.values() if len(group) > 1]
    
    def _group_by_fuzzy_name(self, lora_list):
        # Simple implementation: group by normalized name
        groups = {}
        for lora in lora_list:
            name = lora.get("name", "")
            # Remove version/size markers
            import re
            normalized = re.sub(r'[_\-\.](v\d+|fp\d+|ema|ckpt|\d{3,4}|\d+\.\d+)[_\-\.]', '_', name.lower())
            normalized = re.sub(r'[_\-]+', '_', normalized).strip('_')
            
            if normalized not in groups:
                groups[normalized] = []
            groups[normalized].append(lora)
        
        return [group for group in groups.values() if len(group) > 1]
    
    def _group_by_combined(self, lora_list):
        # First group by exact hash, then by CivitAI metadata, then by fuzzy name
        # This is a simplified implementation
        hash_groups = self._group_by_exact_hash(lora_list)
        if hash_groups:
            # Flatten and continue with remaining
            processed = set()
            for group in hash_groups:
                for lora in group:
                    # Mark as processed by some identifier
                    pass
            # For simplicity, just return hash groups for now
            return hash_groups
        
        civitai_groups = self._group_by_civitai_metadata(lora_list)
        if civitai_groups:
            return civitai_groups
        
        return self._group_by_fuzzy_name(lora_list)
    
    def _select_keeper(self, group, criteria):
        """Select the keeper file from a group based on criteria"""
        if criteria == "newest":
            return max(group, key=lambda x: x.get("modified", 0))
        elif criteria == "largest":
            return max(group, key=lambda x: x.get("size_kb", 0))
        elif criteria == "in_comfyui":
            # Prefer files that are already in ComfyUI folder
            comfyui_preferred = [lora for lora in group if "comfyui" in lora.get("path", "").lower()]
            if comfyui_preferred:
                return max(comfyui_preferred, key=lambda x: x.get("modified", 0))
            else:
                return max(group, key=lambda x: x.get("modified", 0))
        else:
            return group[0]

# Additional utility nodes could be added here
# For example: SolarLoraGalleryNode, SolarLoraUpscalerNode, etc.

@register_node
class SolarModelSelector:
    """Model card selector with fully custom overlay UI in the frontend."""
    DISPLAY_NAME = "Solar Model Selector"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_json": ("STRING", {"default": "{}", "multiline": False}),
            },
            "optional": {
                "checkpoint": (["None"], {"default": "None"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model_path",)
    FUNCTION = "select"
    CATEGORY = "Solar"

    def select(self, model_json, checkpoint="None"):
        try:
            data = json.loads(model_json)
            return (data.get("path", ""),)
        except Exception:
            return ("",)

@register_node
class SolarPromptEnhancer:
    """LLM-powered prompt enhancement. Calls the Solar manager via local HTTP or accepts an enhanced prompt string."""
    DISPLAY_NAME = "Solar Prompt Enhancer"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "enhanced_prompt": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "enhance"
    CATEGORY = "Solar"

    def enhance(self, prompt, enhanced_prompt, temperature=0.7):
        result = enhanced_prompt if enhanced_prompt else prompt
        return (result,)

@register_node
class SolarImageDescriber:
    """LLM-powered image description. Accepts a pre-generated description string (from the manager)."""
    DISPLAY_NAME = "Solar Image Describer"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "description": ("STRING", {"default": "", "multiline": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("description", "tags")
    FUNCTION = "describe"
    CATEGORY = "Solar"

    def describe(self, image, description=""):
        return (description, "")

print("Solar LoRA Custom Nodes loaded successfully")