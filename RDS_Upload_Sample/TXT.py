


class_path='./088_nef.txt'




with open(class_path) as class_file:
    classes = class_file.readlines()
classes = [c.strip() for c in classes]
print(classes[0])