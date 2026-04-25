# nanoScore 

**nanoScore** is a standalone desktop application developed to assist in the transcription and score reconstruction of historical vocal partbooks. 

Created as a Bachelor's thesis project, this tool streamlines the transition from archival digitized manuscripts to modern, machine-readable musical analysis. The current release is specifically trained and optimized for 17th-century mensural notation printed in the Ballard typography style. By processing individual vocal parts from scanned PDFs, the software utilizes a multi-stage deep learning approach to extract historical music notation and generate unified `MusicXML` scores, significantly reducing the manual labor traditionally required for historical transcription.


## Key Features

* **Dual Transcription Workflows:**
  * **Automatic Mode:** A fully automated workflow that processes raw PDFs through the multi-stage OMR pipeline, generating a synchronized MusicXML score without requiring manual intervention during the extraction process.
  * **Semiautomatic (Human-in-the-Loop) Mode:** An interactive workflow designed to maximize transcription accuracy when dealing with degraded or highly complex historical manuscripts. The pipeline halts at critical inference junctures, allowing the user to review, manually draw, delete, or adjust bounding boxes and symbols on an interactive PyQt6 vector canvas before proceeding.
* **Multi-Stage Vision Pipeline:** Utilizes a custom three-stage AI architecture powered by Ultralytics YOLO11 (Object Detection & Image Classification).
* **Semantic Score Reconstruction:** Transforms spatial object coordinates into structured music theory. The engine algorithmically resolves note pitches based on active clefs, computes rhythm divisions (accounting for historical features like augmentation dots and coloration), and logically groups events into measures.
* **Multi-Voice Synchronization:** Mathematically aligns disparate historical vocal parts (which often lack synchronized barlines) to assemble a structurally cohesive master score.
* **Automated Validation:** Generates a post-transcription validation report that analyzes the mathematical duration of every measure across all voices, flagging rhythmic inconsistencies to facilitate efficient manual correction.


## Usage

1. Launch **nanoScore** and click **+ Create new project** from the main menu.
2. Enter a project name and upload one or more PDF files corresponding to the historical voices (e.g., Soprano, Alto, Tenor, Bass).
3. Choose either **Automatic** or **Semiautomatic** transcription mode.
4. If using Semiautomatic mode, follow the UI prompts to validate the Staff bounding boxes and Notation symbols. Use the built-in tools to correct any AI mistakes.
5. Once processing finishes, view the validation results and click **Export copy** to save your `.musicxml` file.
6. Open the exported file in standard notation software (MuseScore, Sibelius, Finale) for playback and formatting!


## Installation

1. Navigate to the **[Releases](../../releases)** tab on the right side of this GitHub page.
2. Download the latest `nanoScore_v1.0.0_setup.exe` file.
3. Run the installer.


## Screenshots

![start_screen](https://github.com/user-attachments/assets/bb4c4911-ad8c-479c-a70f-7552e6316bf7)
![create_project](https://github.com/user-attachments/assets/672b91ee-a7c2-4356-88f3-39543c1b442f)
![progress_screen](https://github.com/user-attachments/assets/6a667ecd-7356-4856-a462-d871aee9deda)
![validate_staves](https://github.com/user-attachments/assets/4f998988-e206-4b38-9b48-f31483e3d2ff)
![validate_notation](https://github.com/user-attachments/assets/a7d408e8-8d6e-4bcc-bbae-da1c9c44257e)
