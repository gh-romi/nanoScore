import os
import time
from ultralytics import YOLO
from typing import List, Union

class YoloInferenceEngine:
    """
    A class to encapsulate the YOLO object detection inference process.
    It uses the 'ultralytics' library to load a model and run predictions.
    """

    def __init__(self, model_path: str):
        """
        Initializes the YoloInferenceEngine.

        Args:
            model_path (str): The path to the YOLO model file (e.g., .pt or .onnx).
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at: {model_path}")
        
        # Load the model using the ultralytics library.
        # The library handles the specifics of loading .pt, .onnx, etc.
        self.model = YOLO(model_path)
        print("YOLO model loaded successfully.")

    def predict_staff(self, 
                         input_folder: str, 
                         conf: float = 0.25, 
                         iou: float = 0.4,
                         save: bool = False,
                         save_txt: bool = False,
                         name: str = "yolo_predictions",
                         progress_callback=None) -> List:
        """
        Runs prediction on all images within a specified folder.

        Args:
            input_folder (str): Path to the folder containing images.
            conf (float): Confidence threshold for predictions.
            iou (float): Intersection over Union (IoU) threshold for NMS.
            save (bool): Whether to save images with bounding boxes.
            save_txt (bool): Whether to save results to a .txt file.
            name (str): The name of the subfolder for saving results.

        Returns:
            List: A list of ultralytics Results objects, one for each image.
        """
        if not os.path.isdir(input_folder):
            raise NotADirectoryError(f"Input path is not a directory: {input_folder}")

        print(f"Starting prediction on folder: {input_folder}")
        start_time = time.time()

        # The model.predict method can take a directory path directly.
        # We'll run prediction in stream mode for memory efficiency.
        results_generator = self.model.predict(
            source=input_folder,
            conf=conf,
            iou=iou,
            save=save,
            save_txt=save_txt,
            save_conf=True,        # Always save confidence scores in txt if save_txt is True
            device='cpu',          # Forcing CPU for consistency as per original script
            stream=True,           # Process images one by one
            batch=1,               # Enforced batch=1
            exist_ok=True,         # Overwrite existing prediction folder
            name=name # Default output subfolder name
        )

        valid_exts = {'.png', '.jpg', '.jpeg', '.pdf', '.tiff', '.bmp'}
        total_files = len([f for f in os.listdir(input_folder) if os.path.splitext(f)[1].lower() in valid_exts])

        # Iterate through the generator to get all results
        results_list = []
        for i, result in enumerate(results_generator):
            results_list.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total_files)
            # You could add more detailed per-image processing here if needed
            # For example, printing the number of boxes found in each image:
            # print(f"Found {len(result.boxes)} objects in {os.path.basename(result.path)}")

        end_time = time.time()
        total_seconds = end_time - start_time
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        
        print(f"Prediction complete for folder '{input_folder}'.")
        print(f"Processing took {minutes} minutes and {seconds} seconds.")
        
        return results_list

    def predict_notes(self, 
                         input_folder: str, 
                         conf: float = 0.1, 
                         iou: float = 0.2,
                         save: bool = False,
                         save_txt: bool = False,
                         name: str = "yolo_predictions",
                         progress_callback=None) -> List:
        """
        Runs notes prediction on all cropped staff images within a specified folder.
        Uses specialized NMS settings for dense objects like musical notes.
        """
        if not os.path.isdir(input_folder):
            raise NotADirectoryError(f"Input path is not a directory: {input_folder}")

        print(f"Starting notes prediction on folder: {input_folder}")
        start_time = time.time()

        results_generator = self.model.predict(
            source=input_folder,
            conf=conf,
            iou=iou,
            save=save,
            save_txt=save_txt,
            save_conf=True,        
            device='cpu',          
            stream=True,           
            batch=1,               
            exist_ok=True,         
            name=name,
            agnostic_nms=True,     # Critical for notes (preventing overlaps between classes)
            line_width=1           # Thinner lines for small objects
        )

        valid_exts = {'.png', '.jpg', '.jpeg', '.pdf', '.tiff', '.bmp'}
        total_files = len([f for f in os.listdir(input_folder) if os.path.splitext(f)[1].lower() in valid_exts])

        results_list = []
        for i, result in enumerate(results_generator):
            results_list.append(result)
            if progress_callback:
                progress_callback(i + 1, total_files)

        end_time = time.time()
        total_seconds = end_time - start_time
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        
        print(f"Prediction complete for folder '{input_folder}'.")
        print(f"Processing took {minutes} minutes and {seconds} seconds.")
        
        return results_list

    def classify_position(self, 
                          input_folder: str, 
                          save: bool = False,
                          save_txt: bool = False,
                          name: str = "yolo_classification",
                          progress_callback=None) -> List:
        """
        Runs position classification on square-padded cropped symbols.
        Uses verbose=False to minimize terminal spam during high-volume processing.
        """
        if not os.path.isdir(input_folder):
            raise NotADirectoryError(f"Input path is not a directory: {input_folder}")

        print(f"Starting position classification on folder: {input_folder}")
        start_time = time.time()

        results_generator = self.model.predict(
            source=input_folder,
            save=save,
            save_txt=save_txt,
            save_conf=True,        
            device='cpu',          
            stream=True,           
            batch=1,               
            exist_ok=True,         
            name=name,
            verbose=False          # Kills the terminal spam for high volume
        )

        valid_exts = {'.png', '.jpg', '.jpeg', '.pdf', '.tiff', '.bmp'}
        total_files = len([f for f in os.listdir(input_folder) if os.path.splitext(f)[1].lower() in valid_exts])

        results_list = []
        for i, result in enumerate(results_generator):
            results_list.append(result)
            if progress_callback:
                if i == 0 or (i + 1) % 50 == 0 or (i + 1) == total_files:
                    val = f">{i + 1}" if (i + 1) < total_files else total_files
                    progress_callback(val, total_files)

        end_time = time.time()
        total_seconds = end_time - start_time
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        
        print(f"Classification complete for folder '{input_folder}'.")
        print(f"Processing took {minutes} minutes and {seconds} seconds.")
        
        return results_list

# Example of how to use this class (for demonstration)
if __name__ == '__main__':
    # This block will only run when the script is executed directly
    # It will not run when the class is imported.
    
    # --- CONFIGURATION ---
    # Use one of the provided model paths
    # MODEL_PATH = "yolo11n_staff_prediction.pt"
    MODEL_PATH = "yolo11n_notes_prediction.pt" 
    
    # Define the folder with images to process
    # This should be a folder containing .jpg, .png, etc. image files
    INPUT_IMAGE_FOLDER = "data/PNG_images_04" # This is an example, update if needed

    print("--- Starting YOLO Inference Engine Demonstration ---")
    
    try:
        # 1. Initialize the engine with the model path
        inference_engine = YoloInferenceEngine(model_path=MODEL_PATH)

        # 2. Run prediction on the folder
        #    save=True will save annotated images to a 'runs/detect/yolo_predictions' folder
        #    save_txt=True will save bounding box data to text files
        if os.path.isdir(INPUT_IMAGE_FOLDER):
            list_of_results = inference_engine.predict_staff(
                input_folder=INPUT_IMAGE_FOLDER,
                conf=0.25,
                save=True,
                save_txt=True
            )

            print(f"Successfully processed {len(list_of_results)} images.")

            # 3. Inspect the first result (optional)
            if list_of_results:
                first_result = list_of_results[0]
                print(f"--- Details for the first image ({os.path.basename(first_result.path)}) ---")
                print(f"Image shape: {first_result.orig_shape}")
                
                boxes = first_result.boxes
                print(f"Found {len(boxes)} objects.")
                
                # Print details of the first 5 boxes
                for i, box in enumerate(boxes[:5]):
                    class_id = int(box.cls)
                    class_name = inference_engine.model.names[class_id]
                    confidence = float(box.conf)
                    coords = box.xyxy[0].tolist()
                    print(f"  Box {i+1}: Class='{class_name}', Conf={confidence:.2f}, Coords={coords}")

        else:
            print(f"Demonstration skipped: Input folder '{INPUT_IMAGE_FOLDER}' not found.")
            print("Please create this folder and add images to it to run the demo.")

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Please ensure the model path and image folder paths are correct.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    print("--- Demonstration Finished ---")
