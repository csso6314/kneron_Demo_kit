
import os
import sys
import platform
import argparse
import time
import threading

PWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(PWD, '..'))
MODEL_PATH = os.path.join(PWD, '../../res/models/KL520/tiny_yolo_v3/')
class_path='../../res/models/KL520/tiny_yolo_v3/' 


model_name=input('model:')
MODEL_PATH=MODEL_PATH+model_name+'.nef'
MODEL_FILE_PATH = os.path.join(PWD, MODEL_PATH)
class_path=class_path+model_name+'.txt'
print(MODEL_FILE_PATH)
print(class_path)



