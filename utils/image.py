import os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def get_decimal_from_dms(dms, ref):
    """
    Convert DMS (Degrees Minutes Seconds) to decimal format.
    """
    degrees = dms[0]
    minutes = dms[1]
    seconds = dms[2]
    
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    if ref in ['S', 'W']:
        decimal = -decimal
        
    return decimal

def get_gps_from_image(image_source):
    """
    Extract GPS from an image path (str) or PIL Image object.
    Returns (latitude, longitude) or (None, None).
    """
    try:
        if isinstance(image_source, str):
            image = Image.open(image_source)
        else:
            image = image_source
            
        exif = image._getexif()
        if not exif:
            return None, None
            
        gps_info = {}
        for tag, value in exif.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_info[sub_decoded] = value[t]
        
        if not gps_info:
            return None, None
            
        lat = None
        lon = None
        
        if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
            lat = get_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef'])
            
        if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
            lon = get_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
            
        return lat, lon
    except Exception as e:
        print(f"Error extracting GPS: {e}")
        return None, None

def extract_timestamp_from_image(image: Image.Image):
    """
    Extracts the full datetime object from valid EXIF.
    Returns datetime or None.
    """
    from datetime import datetime
    
    try:
        # 1. Try getexif()
        exif = image.getexif()
        for tag_id in [36867, 36868, 306]:
            if tag_id in exif:
                date_str = exif[tag_id]
                try:
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    continue
        
        # 2. Try _getexif()
        raw_exif = image._getexif()
        if raw_exif:
            for tag, value in raw_exif.items():
                decoded = TAGS.get(tag, tag)
                if decoded in ('DateTimeOriginal', 'DateTime', 'DateTimeDigitized'):
                    try:
                        return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Error extracting timestamp: {e}")
        
    return None

def extract_date_from_image(image: Image.Image) -> str | None:
    """
    Wrapper to get YYYY-MM-DD string.
    """
    dt = extract_timestamp_from_image(image)
    if dt:
        return dt.strftime('%Y-%m-%d')
    return None
