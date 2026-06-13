import os
import torch
import numpy as np
from dotenv import load_dotenv
load_dotenv()
from pyannote.audio import Model, Inference
from pyannote.core import Segment

def test():
    HF_TOKEN = os.getenv("HF_TOKEN")
    print("Loading model...")
    # WhisperX diarization pipeline usually downloads this model
    model = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM", use_auth_token=HF_TOKEN)
    if model is None:
        print("Falling back to pyannote/embedding")
        model = Model.from_pretrained("pyannote/embedding", use_auth_token=HF_TOKEN)
        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    inference = Inference(model, window="whole")
    print("Success! Model loaded.")

if __name__ == "__main__":
    test()
