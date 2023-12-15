import cv2
import numpy as np

cap = cv2.VideoCapture(0)                 # 讀取攝影鏡頭
w = 420
h = 240
draw = np.zeros((h,w,4), dtype='uint8')


def show_xy(event,x,y,flags,param):
    global dots, draw
    if event == 4:
        cap.release()       # 釋放資源
        cv2.destroyAllWindows()
        #dots.append([x,y])


cv2.imshow('oxxostudio', draw)
cv2.setMouseCallback('oxxostudio', show_xy)

while True:
    ret, _image_to_inference = cap.read()               # 讀取影片的每一個影格
    
    #img = cv2.resize(img,(w,h))         # 縮小尺寸，加快運算速度
    # 透過 for 迴圈合成影像
    cv2.imshow('oxxostudio', _image_to_inference)
    


cap.release()       # 釋放資源
cv2.destroyAllWindows()