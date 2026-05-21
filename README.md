# nanoScore 

**nanoScore** is a standalone desktop application developed to assist in the transcription and score reconstruction of historical vocal partbooks. 

Created as a Bachelor's thesis project, this software is designed for the automated transcription and full score reconstruction of historical vocal books into a machine-readable format. The current release is specifically limited to 17th-century white mensural notation printed by the Ballard press. By processing individual vocal parts from scanned PDFs, the software utilizes a multi-stage deep learning approach to extract historical music notation and generate unified MusicXML scores. This automated reconstruction yields a playable digital score, successfully bypassing the manual transcription bottleneck and allowing for direct sound assessment.


## Key Features

* **Dual Transcription Workflows:**
  * **Automatic Mode:** A fully automated workflow that processes raw PDFs through the multi-stage OMR pipeline, generating a synchronized MusicXML score without requiring manual intervention during the extraction process.
  * **Semiautomatic (Human-in-the-Loop) Mode:** An interactive workflow designed to maximize transcription accuracy when dealing with degraded or highly complex historical manuscripts. The software stops at key checkpoints, allowing the user to review, manually draw, delete or adjust bounding boxes and symbols on an interactive canvas before proceeding.
* **Multi-Stage Vision Pipeline:** Utilizes the three-stage (staff detection, symbol detection, position classification) AI architecture powered by Ultralytics YOLO11n.
* **Semantic Score Reconstruction:** Transforms spatial object coordinates into structured music theory. The engine algorithmically resolves note pitches based on active clefs, computes rhythm divisions (accounting for historical features like augmentation dots and coloration), and logically groups events into measures.
* **Multi-Voice Synchronization:** Aligns different historical vocal parts to assemble a structurally cohesive final multi-voice score.
* **Automated Validation:** Generates a post-transcription validation report that analyzes the mathematical duration of every measure across all voices, flagging rhythmic inconsistencies to facilitate efficient manual correction.


## PDF Input Requirements

To ensure accurate AI processing and proper multi-voice synchronization, please follow these guidelines for your input PDFs:

* **Page Synchronization:** The layout must match across all uploaded files. The actual sheet music needs to start on the exact same page number for every voice (e.g., if the Soprano notation starts on page 4, the Alto, Tenor, and Bass must also start on page 4). 
* **Clean Inputs (Recommended):** It is highly recommended to remove any modern library inserts (like "About" or copyright pages) from the beginning of the PDF. Original historical pages that simply don't have music on them are perfectly fine to keep.
* **Proper PDF Editing (Avoid "Print to PDF"):** If you need to split a document or delete pages, use a PDF editor (like iLovePDF or PicoPDF). Never use "Print to PDF" to save pages, as it will break the image formatting.
* **Single-Page Spreads:** Each PDF page should contain only one scanned page. For the current version of the software two-page book spreads should be cropped into individual pages before uploading.


## Usage

1. Launch **nanoScore** and click **+ Create new project** from the main menu.
2. Enter a project name and upload one or more PDF files corresponding to the historical voices (e.g., Soprano, Alto, Tenor, Bass).
3. Choose either **Automatic** or **Semiautomatic** transcription mode.
4. If using Semiautomatic mode, follow the UI prompts to validate the Staff bounding boxes and Notation symbols. Use the built-in tools to correct any AI mistakes.
5. Once processing finishes, view the validation results and click **Export copy** to save your `.musicxml` file.
6. Open the exported file in standard notation software (MuseScore, Sibelius, Finale) for playback and formatting.


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
