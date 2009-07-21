# myapp/specs.py

from imagekit.specs import ImageSpec 
from imagekit import processors 
import os
from PIL import Image
class ExifRotate(processors.ImageProcessor):
    """Autorotates an image based on exif orientation"""
    method={1:[],
            2:[Image.FLIP_LEFT_RIGHT],
            3:[Image.ROTATE_180],
            4:[Image.FLIP_TOP_BOTTOM],
            5:[Image.ROTATE_270, Image.FLIP_LEFT_RIGHT],
            6:[Image.ROTATE_270],
            7:[Image.ROTATE_90, Image.FLIP_LEFT_RIGHT],
            8:[Image.ROTATE_90],
            }
    @classmethod
    def process(cls, img, fmt, obj):
        try:
            if obj is not None:
                orient = int(obj.EXIF['Image Orientation'].values[0])
            else:
                orient = img._getexif()[274]#Orientation tag

            for step in cls.method[orient]:
                img=img.transpose(step)
        except AttributeError:
            pass
        return img, fmt
            

# first we define our thumbnail resize processor 
class ResizeThumb(processors.Resize): 
    width = 120
    height = 120
    crop = True

class ResizeSmallThumb(processors.Resize):
    width = 75
    height = 75
    crop = True

# now we define a display size resize processor
class ResizeDisplay(processors.Resize):
    width = 600
    height = 400
    crop = False 

# now lets create an adjustment processor to enhance the image at small sizes 
class EnchanceThumb(processors.Adjustment): 
    contrast = 1.2
    sharpness = 1.1 

class Preprocess(ImageSpec):
    quality=90
    processors = [ExifRotate]

class SmallThumb(ImageSpec):
    pre_cache = True
    processors = [ResizeSmallThumb]
    quality = 90

# now we can define our thumbnail spec
class Thumbnail(ImageSpec): 
    access_as = 'thumbnail' 
    pre_cache = True 
    processors = [ResizeThumb] 
    quality = 90

# and our display spec
class Display(ImageSpec):
    increment_count = True
    pre_cache=True
    processors = [ResizeDisplay]
    quality = 90

