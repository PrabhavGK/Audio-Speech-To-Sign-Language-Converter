import nltk
import os

def download_resources():
    # Set the NLTK data directory to a local folder in the project
    nltk_data_dir = os.path.join(os.path.dirname(__file__), 'nltk_data')
    if not os.path.exists(nltk_data_dir):
        os.makedirs(nltk_data_dir)
    nltk.data.path.append(nltk_data_dir)
    nltk.download('punkt', download_dir=nltk_data_dir)

if __name__ == "__main__":
    download_resources()
    print("NLTK 'punkt' resource downloaded successfully to local nltk_data directory.")
