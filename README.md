ParkPulsProj
Overview

This repository contains the analytical workflow for the ParkPulse project. Data pre-processing and processing (incl. natural language processing steps and plotting) is numbered by order of execution as later stages mostly rely on outputs produced earlier in the pipeline. Additional scrips are for variable construction, statistical analysis and an interactive streamlit app to visualise the results.

Workflow

The preprocessing stage prepares and cleans the raw data to ensure consistency and usability in later steps. This is followed by linguistic processing (sentiment and topic modelling).

Subsequent scripts focus on constructing analytical variables, transforming the processed data into features suitable for analysis. These variables are then used in statistical testing and modelling scripts, which generate the results that underpin the project’s findings. 

Streamlit Application

The repository also includes a Streamlit application for interactive visualisation of the results. The app is located in a separate folder and is designed to make the outputs of the analysis more accessible and easier to explore. Rather than relying solely on static results, the interface allows users to engage dynamically with the data and findings.

Running the Project

To run the project, clone the repository and install the required dependencies. The scripts should then be executed in numerical order to ensure that all intermediate datasets are created correctly. However, the original datasets used are not included as some of them, including the main input of comments, is not publicly available. To run the script without edits requires aquisition of the datasets. Even though the scripts are very tailored to the orignal datasets, it is also possible to use other inputs if customisation is applied. 
