import os
import json
import fitz  # PyMuPDF
from pathlib import Path
from engines.yolo_engine import YoloInferenceEngine

class TranscriptionPipeline:
    """
    Orchestrates the automatic transcription workflow. 
    Manages file creation, model routing, and JSON state persistence.
    """
    
    def __init__(self, staff_model_path="yolo11n_staff_prediction.pt"):
        # Initialize the YOLO engine for the staff prediction
        self.staff_engine = YoloInferenceEngine(model_path=staff_model_path)
        
    def run_automatic_pipeline(self, project_name: str, voices_data: list):
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
        
        for idx, voice in enumerate(voices_data, start=1):
            voice_folder_name = f"Voice_{idx:02d}"
            voice_dir = base_dir / voice_folder_name
            images_dir = voice_dir / "page_images"
            
            images_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_path = voice.get("pdf_path")
            if not pdf_path or not os.path.exists(pdf_path):
                print(f"Skipping {voice_folder_name} - invalid or missing PDF path.")
                continue
                
            # --- 1. PDF to JPG Extraction ---
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
            
            # --- 2. Predict Staffs ---
            print(f"Starting staff prediction for {voice_folder_name}...")
            
            # TODO: DELETE save=True (used for testing output right now)
            results = self.staff_engine.predict_staff(
                input_folder=str(images_dir),
                save=True, 
                name=f"{project_name}_{voice_folder_name}_staffs"
            )
            
            # --- 3. Save initial JSON Structure ---
            pages_data = []
            for page_idx, result in enumerate(results, start=1):
                image_name = os.path.basename(result.path)
                img_h, img_w = result.orig_shape
                
                staves_data = []
                if result.boxes:
                    # Sort staves vertically (top to bottom) based on the y1 coordinate
                    sorted_boxes = sorted(result.boxes, key=lambda b: b.xyxy[0][1].item())
                    
                    for staff_idx, box in enumerate(sorted_boxes):
                        xyxy = box.xyxy[0].tolist()    # [x1, y1, x2, y2]
                        xywhn = box.xywhn[0].tolist()  # [x_center, y_center, width, height] normalized
                        conf = box.conf[0].item()
                        
                        base_name = os.path.splitext(image_name)[0]
                        staff_img_name = f"{base_name}_staff_{staff_idx}.jpg"
                        
                        staves_data.append({
                            "staff_number": staff_idx,
                            "staff_image_path": staff_img_name,
                            "staff_image_width": int(xyxy[2] - xyxy[0]),
                            "staff_image_height": int(xyxy[3] - xyxy[1]),
                            "staff_confidence": round(conf, 4),
                            "staff_box_absolute_xyxy": [round(c, 2) for c in xyxy],
                            "staff_box_relative_xywh": [round(c, 4) for c in xywhn],
                            "symbols": [] # Placeholder for next steps in the pipeline
                        })
                
                pages_data.append({
                    "page_id": page_idx,
                    "page_image_path": image_name,
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