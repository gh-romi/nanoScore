import os
import json
import fitz  # PyMuPDF
import cv2
from pathlib import Path
from engines.yolo_engine import YoloInferenceEngine
from engines.data_process_engine import DataProcessEngine

class TranscriptionPipeline:
    """
    Orchestrates the automatic transcription workflow. 
    Manages file creation, model routing, and JSON state persistence.
    """
    
    def __init__(self, staff_model_path="yolo11n_staff_prediction.pt", notes_model_path="yolo11n_notes_prediction.pt", position_model_path="yolo11n-cls_position_classification.pt"):
        # Initialize the YOLO engines
        self.staff_engine = YoloInferenceEngine(model_path=staff_model_path)
        self.notes_engine = YoloInferenceEngine(model_path=notes_model_path)
        self.position_engine = YoloInferenceEngine(model_path=position_model_path)
        
    def run_automatic_pipeline(self, project_name: str, voices_data: list, step_callback=None, voice_progress_callback=None, general_progress_callback=None):
        """
        Executes the first phase of automatic notes transcription.
        
        Args:
            project_name (str): The chosen name for the project.
            voices_data (list): A list of dictionaries containing voice details.
                                e.g., [{'name': 'Soprano', 'pdf_path': 'path/to/file.pdf'}, ...]
        """
        # Fallback if the user left the project name empty
        if not project_name.strip():
            # Find the next available default project name
            i = 1
            while True:
                candidate = f"Project_{i:04d}"
                if not (Path("Projects") / candidate).exists():
                    project_name = candidate
                    break
                i += 1
            
        # Create master project folder
        base_dir = Path("Projects") / project_name
        base_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Started Automatic Pipeline for project: {project_name}")
        


        # --- PHASE 1: Staff Detection & Cropping ---
        print("\n--- Starting Phase 1: Staff Detection & Cropping ---")
        if step_callback: step_callback(1)
        for idx, voice in enumerate(voices_data, start=1):
            if voice_progress_callback: voice_progress_callback(idx - 1, "processing", 0, "?")
            voice_folder_name = f"Voice_{idx:02d}"
            voice_dir = base_dir / voice_folder_name
            images_dir = voice_dir / "page_images"
            staff_images_dir = voice_dir / "Staff_images"
            
            images_dir.mkdir(parents=True, exist_ok=True)
            staff_images_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_path = voice.get("pdf_path")
            if not pdf_path or not os.path.exists(pdf_path):
                print(f"Skipping {voice_folder_name} - invalid or missing PDF path.")
                continue
                
            # 1. PDF to JPG Extraction
            print(f"Extracting images from {os.path.basename(pdf_path)} into {images_dir}...")
            doc = fitz.open(pdf_path)
            image_counter = 1
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    image_name = f"{image_counter:04d}.{image_ext}"
                    image_path = images_dir / image_name
                    
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)
                        
                    image_counter += 1
            
            # 2. Predict Staves
            print(f"Starting staff prediction for {voice_folder_name}...")
            
            # TODO: DELETE save=True (used for testing output right now)
            results = self.staff_engine.predict_staff(
                input_folder=str(images_dir),
                #save=True, 
                name=f"{project_name}_{voice_folder_name}_staves",
                progress_callback=(lambda c, t, i=idx: voice_progress_callback(i - 1, "processing", c, t)) if voice_progress_callback else None
            )
            
            # 3. Crop Staves & Save initial JSON Structure
            pages_data = []
            EXPAND_W = 0.05
            EXPAND_H = 0.50
            
            for page_idx, result in enumerate(results, start=1):
                image_name = os.path.basename(result.path)
                img_h, img_w = result.orig_shape
                
                # Load original image for cropping
                img = cv2.imread(result.path)
                if img is None:
                    print(f"Warning: Could not read {result.path} for cropping. Skipping.")
                    continue
                
                staves_data = []
                if result.boxes:
                    # Sort staves vertically (top to bottom) based on y_center, then horizontally (left to right) based on x_center
                    sorted_boxes = sorted(result.boxes, key=lambda b: (b.xywhn[0][1].item(), b.xywhn[0][0].item()))
                    
                    for staff_idx, box in enumerate(sorted_boxes):
                        xyxy = box.xyxy[0].tolist()    # [x1, y1, x2, y2]
                        xywhn = box.xywhn[0].tolist()  # [x_center, y_center, width, height] normalized
                        conf = box.conf[0].item()
                        
                        # --- Calculate Staff Box Expansion ---
                        x_c_norm, y_c_norm, w_norm, h_norm = xywhn
                        new_w_norm = w_norm * (1 + EXPAND_W)
                        new_h_norm = h_norm * (1 + EXPAND_H)
                        
                        x1 = int((x_c_norm - new_w_norm / 2) * img_w)
                        y1 = int((y_c_norm - new_h_norm / 2) * img_h)
                        x2 = int((x_c_norm + new_w_norm / 2) * img_w)
                        y2 = int((y_c_norm + new_h_norm / 2) * img_h)
                        
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(img_w, x2), min(img_h, y2)
                        
                        # --- Crop and Save ---
                        base_name = os.path.splitext(image_name)[0]
                        staff_img_name = f"{base_name}_staff_{staff_idx}.jpg"
                        staff_save_path = staff_images_dir / staff_img_name
                        
                        crop = img[y1:y2, x1:x2]
                        if crop.size > 0:
                            cv2.imwrite(str(staff_save_path), crop)
                            crop_h, crop_w = crop.shape[:2]
                        else:
                            print(f"Warning: Calculated empty crop for {staff_img_name}")
                            crop_h, crop_w = int(xyxy[3] - xyxy[1]), int(xyxy[2] - xyxy[0])
                        
                        staff_image_rel_path = staff_save_path.as_posix()
                        
                        staves_data.append({
                            "staff_number": staff_idx,
                            "staff_image_path": staff_image_rel_path,
                            "staff_image_width": crop_w,
                            "staff_image_height": crop_h,
                            "staff_confidence": round(conf, 4),
                            "staff_box_absolute_xyxy": [round(c, 2) for c in xyxy],
                            "staff_box_relative_xywh": [round(c, 4) for c in xywhn],
                            "symbols": [] # Placeholder for next steps in the pipeline
                        })
                
                page_image_rel_path = (images_dir / image_name).as_posix()
                pages_data.append({
                    "page_id": page_idx,
                    "page_image_path": page_image_rel_path,
                    "image_width": img_w,
                    "image_height": img_h,
                    "staves": staves_data
                })

            voice_json_data = {
                "voice_number": idx,
                "voice": voice.get("name", voice_folder_name),
                "pdf_path": pdf_path, # Keeping this property as it's useful for state management
                "pages": pages_data
            }
            
            json_path = voice_dir / f"{voice_folder_name}_data.json"
            with open(json_path, "w", encoding="utf-8") as json_file:
                json.dump(voice_json_data, json_file, indent=4)
                
            print(f"Successfully created JSON payload for {voice_folder_name} at {json_path}")
            if voice_progress_callback: voice_progress_callback(idx - 1, "done", len(results), len(results))



        # --- PHASE 2: Notes Detection & JSON Update ---
        print("\n--- Starting Phase 2: Notes Detection ---")
        if step_callback: step_callback(2)
        for idx, voice in enumerate(voices_data, start=1):
            voice_folder_name = f"Voice_{idx:02d}"
            if voice_progress_callback: voice_progress_callback(idx - 1, "processing", 0, "?")
            voice_dir = base_dir / voice_folder_name
            staff_images_dir = voice_dir / "Staff_images"
            json_path = voice_dir / f"{voice_folder_name}_data.json"
            
            if not staff_images_dir.exists() or not any(staff_images_dir.iterdir()):
                continue
                
            print(f"Starting notes prediction for {voice_folder_name}...")
            
            # TODO: DELETE save=True (used for testing output right now)
            results = self.notes_engine.predict_notes(
                input_folder=str(staff_images_dir),
                #save=True, 
                name=f"{project_name}_{voice_folder_name}_notes",
                progress_callback=(lambda c, t, i=idx: voice_progress_callback(i - 1, "processing", c, t)) if voice_progress_callback else None
            )
            
            # Load JSON to dynamically update
            with open(json_path, "r", encoding="utf-8") as f:
                voice_json_data = json.load(f)
                
            # Build a quick lookup dictionary for staves using the basename of the staff image
            staff_dict_map = {}
            for page in voice_json_data["pages"]:
                for staff in page["staves"]:
                    staff_basename = os.path.basename(staff["staff_image_path"])
                    staff_dict_map[staff_basename] = staff
                    
            for result in results:
                img_basename = os.path.basename(result.path)
                if img_basename in staff_dict_map:
                    staff_dict = staff_dict_map[img_basename]
                    
                    symbols_data = []
                    if result.boxes:
                        # Sort notes horizontally (left to right) based on x_center, then vertically (top to bottom) based on y_center
                        sorted_boxes = sorted(result.boxes, key=lambda b: (b.xywhn[0][0].item(), b.xywhn[0][1].item()))
                        
                        for sym_idx, box in enumerate(sorted_boxes):
                            xyxy = box.xyxy[0].tolist()
                            xywhn = box.xywhn[0].tolist()
                            conf = box.conf[0].item()
                            cls_id = int(box.cls[0].item())
                            cls_name = result.names[cls_id]
                            
                            symbols_data.append({
                                "symbol_number": sym_idx,
                                "class_id": cls_id,
                                "class_name": cls_name,
                                "class_confidence": round(conf, 4),
                                "symbol_box_absolute_xyxy": [round(c, 2) for c in xyxy],
                                "symbol_box_relative_xywh": [round(c, 4) for c in xywhn],
                                "position_type": None,
                                "position_number": None,
                                "position_confidence": None
                            })
                            
                    staff_dict["symbols"] = symbols_data
                    
            # Save updated JSON with notes appended
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(voice_json_data, f, indent=4)
                
            print(f"Successfully updated JSON with notes for {voice_folder_name} at {json_path}")
            if voice_progress_callback: voice_progress_callback(idx - 1, "done", len(results), len(results))



        # --- PHASE 3: Symbol Cropping & Position Classification ---
        print("\n--- Starting Phase 3: Position Classification ---")
        TARGET_CLASSES = [0, 2, 5, 7, 8, 15, 16, 17, 18, 19, 20, 21, 22]
        BASE_CROP_WIDTH = 80
        F_CLEF_WIDTH = 95  # 50 + 15px
        
        if step_callback: step_callback(3)
        for idx, voice in enumerate(voices_data, start=1):
            voice_folder_name = f"Voice_{idx:02d}"
            if voice_progress_callback: voice_progress_callback(idx - 1, "processing", 0, "?")
            voice_dir = base_dir / voice_folder_name
            symbol_crops_dir = voice_dir / "Symbol_crops"
            json_path = voice_dir / f"{voice_folder_name}_data.json"
            
            if not json_path.exists():
                continue
                
            symbol_crops_dir.mkdir(parents=True, exist_ok=True)
            
            with open(json_path, "r", encoding="utf-8") as f:
                voice_json_data = json.load(f)
                
            # Mapping so we can easily connect a crop filename back to the exact JSON dictionary
            crop_to_symbol_map = {}
            
            for page in voice_json_data.get("pages", []):
                for staff in page.get("staves", []):
                    img_path = staff["staff_image_path"]
                    img = cv2.imread(img_path)
                    if img is None:
                        continue
                        
                    img_h, img_w = img.shape[:2]
                    
                    for sym in staff.get("symbols", []):
                        if sym["class_id"] not in TARGET_CLASSES:
                            continue
                            
                        # Convert YOLO normalized coordinates back to absolute pixels for the staff image
                        x_c_norm, y_c_norm, w_norm, h_norm = sym["symbol_box_relative_xywh"]
                        x_c_pixel = int(x_c_norm * img_w)
                        y_c_pixel = int(y_c_norm * img_h)
                        box_w_pixel = int(w_norm * img_w)
                        box_h_pixel = int(h_norm * img_h)
                        
                        # Draw the 2px red highlight rectangle
                        temp_img = img.copy()
                        box_x1 = x_c_pixel - (box_w_pixel // 2)
                        box_y1 = y_c_pixel - (box_h_pixel // 2)
                        box_x2 = x_c_pixel + (box_w_pixel // 2)
                        box_y2 = y_c_pixel + (box_h_pixel // 2)
                        cv2.rectangle(temp_img, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 255), 2)
                        
                        # Calculate full-height crop boundaries
                        crop_width = F_CLEF_WIDTH if sym["class_id"] == 8 else BASE_CROP_WIDTH
                        y1 = 0
                        y2 = img_h
                        x1 = max(0, x_c_pixel - (crop_width // 2))
                        x2 = min(img_w, x_c_pixel + (crop_width // 2))
                        
                        crop = temp_img[y1:y2, x1:x2]
                        if crop.size == 0:
                            continue
                            
                        # Pad crop to a perfect square with (114, 114, 114)
                        h, w = crop.shape[:2]
                        if h != w:
                            max_side = max(w, h)
                            top = (max_side - h) // 2
                            bottom = max_side - h - top
                            left = (max_side - w) // 2
                            right = max_side - w - left
                            crop = cv2.copyMakeBorder(crop, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))
                            
                        staff_basename = os.path.splitext(os.path.basename(img_path))[0]
                        crop_name = f"{staff_basename}_obj_{sym['symbol_number']:03d}.jpg"
                        crop_path = symbol_crops_dir / crop_name
                        
                        cv2.imwrite(str(crop_path), crop)
                        crop_to_symbol_map[crop_name] = sym
                        
            if not any(symbol_crops_dir.iterdir()):
                continue
                
            print(f"Starting position classification for {voice_folder_name}...")
            
            # TODO: DELETE save=True (used for testing output right now)
            results = self.position_engine.classify_position(
                input_folder=str(symbol_crops_dir),
                #save=True,
                name=f"{project_name}_{voice_folder_name}_positions",
                progress_callback=(lambda c, t, i=idx: voice_progress_callback(i - 1, "processing", c, t)) if voice_progress_callback else None
            )
            
            for result in results:
                img_basename = os.path.basename(result.path)
                if img_basename in crop_to_symbol_map:
                    sym = crop_to_symbol_map[img_basename]
                    
                    top1_id = result.probs.top1
                    top1_conf = result.probs.top1conf.item()
                    class_name = result.names[top1_id]
                    
                    # Parse the position class name (e.g., "L5" -> "L", 5 | "S_minus_1" -> "S", -1)
                    if class_name.startswith(("L", "S")) and len(class_name) > 1:
                        sym["position_type"] = class_name[0]
                        num_str = class_name[1:]
                        
                        if "_minus_" in num_str:
                            num_str = num_str.replace("_minus_", "-")
                        elif "minus_" in num_str:
                            num_str = num_str.replace("minus_", "-")
                            
                        try:
                            sym["position_number"] = int(num_str)
                        except ValueError:
                            sym["position_number"] = num_str
                    else:
                        sym["position_type"] = class_name
                        sym["position_number"] = None
                        
                    sym["position_confidence"] = round(top1_conf, 4)
                    
            # Save final updated JSON
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(voice_json_data, f, indent=4)
                
            print(f"Successfully finalized JSON with position classes for {voice_folder_name} at {json_path}")
            if voice_progress_callback: voice_progress_callback(idx - 1, "done", len(results), len(results))


        # --- PHASE 4: Agnostic to Partially Semantic ---
        print("\n--- Starting Phase 4: Agnostic to Partially Semantic ---")
        if step_callback: step_callback(4)
        if general_progress_callback: general_progress_callback("Processing and saving MusicXML files", "processing", 0, 1)
        data_engine = DataProcessEngine()
        
        for idx, voice in enumerate(voices_data, start=1):
            voice_folder_name = f"Voice_{idx:02d}"
            voice_dir = base_dir / voice_folder_name
            json_path = voice_dir / f"{voice_folder_name}_data.json"
            out_json_path = voice_dir / f"{voice_folder_name}_partially_semantic_data.json"
            
            if not json_path.exists():
                continue
                
            print(f"Generating partially semantic data for {voice_folder_name}...")
            
            with open(json_path, "r", encoding="utf-8") as f:
                agnostic_data = json.load(f)
                
            partially_semantic_data = data_engine.process_agnostic_to_partially_semantic(agnostic_data)
            
            with open(out_json_path, "w", encoding="utf-8") as f:
                json.dump(partially_semantic_data, f, indent=4)
                
            print(f"Successfully created partially semantic JSON for {voice_folder_name} at {out_json_path}")


        # --- PHASE 5: Partially Semantic to Fully Semantic ---
        print("\n--- Starting Phase 5: Partially Semantic to Fully Semantic ---")
        
        cheatsheet_path = Path("semantic_cheatsheet.json")
        if not cheatsheet_path.exists():
            print(f"Warning: Cannot find {cheatsheet_path} in the root directory. Phase 5 skipped.")
        else:
            with open(cheatsheet_path, "r", encoding="utf-8") as f:
                cheatsheet = json.load(f)
                
            # 1. Load all partially semantic data into memory
            all_partially_semantic_data = []
            for idx, voice in enumerate(voices_data, start=1):
                voice_folder_name = f"Voice_{idx:02d}"
                voice_dir = base_dir / voice_folder_name
                in_json_path = voice_dir / f"{voice_folder_name}_partially_semantic_data.json"
                out_json_path = voice_dir / f"{voice_folder_name}_semantic_data.json"
                
                if not in_json_path.exists():
                    continue
                    
                with open(in_json_path, "r", encoding="utf-8") as f:
                    partially_semantic_data = json.load(f)
                
                all_partially_semantic_data.append((voice_folder_name, partially_semantic_data, out_json_path))

            # 2. Global Pre-Scan: Check ALL voices for coloration
            global_requires_coloration = False
            for _, p_data, _ in all_partially_semantic_data:
                for p_measure in p_data.get("measures", []):
                    for event in p_measure.get("events", []):
                        if event.get("class_id") == 22:
                            global_requires_coloration = True
                            break
                    if global_requires_coloration: break
                if global_requires_coloration: break

            # 3. Process each voice using the global coloration flag
            all_fully_semantic_data = []
            for voice_folder_name, partially_semantic_data, out_json_path in all_partially_semantic_data:
                print(f"Generating fully semantic data for {voice_folder_name}...")
                
                fully_semantic_data = data_engine.process_partially_semantic_to_semantic(
                    partially_semantic_data, cheatsheet, global_requires_coloration
                )
                
                with open(out_json_path, "w", encoding="utf-8") as f:
                    json.dump(fully_semantic_data, f, indent=4)
                    
                all_fully_semantic_data.append(fully_semantic_data)
                print(f"Successfully created fully semantic JSON for {voice_folder_name} at {out_json_path}")


        # --- PHASE 6: MusicXML Generation & Synchronization ---
        print("\n--- Starting Phase 6: MusicXML Generation & Global Sync ---")
        if not all_fully_semantic_data:
            print("No valid semantic data found to generate MusicXML. Skipping Phase 6.")
            return

        final_score_data = all_fully_semantic_data

        if len(all_fully_semantic_data) == 1:
            # SINGLE VOICE PIPELINE
            voice_name = all_fully_semantic_data[0].get("voice", "Voice_1")
            out_xml_path = base_dir / f"{project_name}.musicxml"
            print(f"Generating MusicXML for single voice: {voice_name}...")
            data_engine.generate_musicxml(all_fully_semantic_data, cheatsheet, str(out_xml_path), project_name)
            print(f"Successfully created {out_xml_path}")
        else:
            # MULTIPLE VOICES PIPELINE
            for v_data in all_fully_semantic_data:
                voice_name = v_data.get("voice", "Unknown_Voice")
                out_xml_path = base_dir / f"{project_name}_{voice_name}.musicxml"
                print(f"Generating individual MusicXML for {voice_name}...")
                data_engine.generate_musicxml([v_data], cheatsheet, str(out_xml_path), project_name)
                
            print("\nSynchronizing global measures across all voices...")
            synced_data = data_engine.sync_voices(all_fully_semantic_data)
            final_score_data = synced_data
            
            # Optional but recommended: Save the fully synchronized data back to JSON for user debugging
            for idx, v_data in enumerate(synced_data, start=1):
                voice_folder_name = f"Voice_{idx:02d}"
                out_json_path = base_dir / voice_folder_name / f"{voice_folder_name}_semantic_data.json"
                with open(out_json_path, "w", encoding="utf-8") as f:
                    json.dump(v_data, f, indent=4)
                    
            combined_xml_path = base_dir / f"{project_name}.musicxml"
            print(f"Generating combined synchronized MusicXML...")
            data_engine.generate_musicxml(synced_data, cheatsheet, str(combined_xml_path), project_name)
            print(f"Successfully created master score at {combined_xml_path}")


        # --- PHASE 7: Duration Validation ---
        print("\n--- Starting Phase 7: Duration Validation ---")
        if final_score_data:
            val_out_path = base_dir / f"{project_name}_validation.json"
            print(f"Generating measure duration validation report...")
            data_engine.generate_duration_validation(final_score_data, str(val_out_path))
            print(f"Successfully created validation report at {val_out_path}")
        if general_progress_callback: general_progress_callback("Processing and saving MusicXML files", "done", 1, 1)