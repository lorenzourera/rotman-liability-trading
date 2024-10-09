# Project Title

## Overview

This project requires setting up a Python virtual environment and installing necessary dependencies. Follow the steps below to get started.

## Getting Started

### Prerequisites

- Git
- Python 3.x
- pip

### Steps

1. **Clone the Repository**

   Open your terminal and run the following command to clone the repository:

   ```bash
   git clone <repository-url>
   ```

   Replace `<repository-url>` with the URL of your Git repository.

2. **Navigate to the Project Directory**

   Change to the project directory:

   ```bash
   cd <repository-name>
   ```

   Replace `<repository-name>` with the name of your cloned repository.

3. **Create a Virtual Environment**

   Create a virtual environment using the following command:

   ```bash
   python -m venv venv
   ```

4. **Activate the Virtual Environment**

   - On Windows:

     ```bash
     venv\Scripts\activate
     ```

   - On macOS/Linux:

     ```bash
     source venv/bin/activate
     ```

5. **Install Dependencies**

   Install the required dependencies using the `requirements.txt` file:

   ```bash
   pip install -r requirements.txt
   ```

6. **Create a `.env` File**

   In the project directory, create a file named `.env` and add the following line:

   ```env
   API_KEY=<your-api-key>
   ```

   Replace `<your-api-key>` with the API key you obtain from the RIT software.

## Running the Project
Run the appropriate script depending on the round

