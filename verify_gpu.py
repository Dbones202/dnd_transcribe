import torch
import sys

def verify():
    print(f"Python Version: {sys.version}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device Name: {torch.cuda.get_device_name(0)}")
        print(f"Device Count: {torch.cuda.device_count()}")
        print(f"Current Device: {torch.cuda.current_device()}")
    else:
        print("CUDA is NOT available.")

if __name__ == '__main__':
    verify()
