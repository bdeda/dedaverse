
import sys
try:
    sys.path.insert(0, r'C:\Program Files\Wing Pro 10')
    import wingdbstub
except ImportError:
    pass
finally:
    sys.path = sys.path[1:]

import exifread
import os
import colorama
import shutil


def main():
    colorama.init()
    
    srcdir = r'D:\photos_to_sort\100MSDCF_3'
    #srcdir = r'D:\amazon_photos\Amazon Photos Downloads\Pictures\albums\Amazon Photos Downloads'
    destdir = r'D:\photos'
    extentions = set()
    count = 0
    for root, dirs, files in os.walk(srcdir):
        dirs = [d for d in dirs if not d.startswith('_')]
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in ('.lrcat', '.db', '.lrprev', '.moff', '.modd', '.m2ts'):
                continue
            count += 1
    index = 0
    for root, dirs, files in os.walk(srcdir):
        dirs = [d for d in dirs if not d.startswith('_')]
        for f in files:
            name, ext = os.path.splitext(f)
            if ext in ('.lrcat', '.db', '.lrprev', '.moff', '.modd', '.m2ts'):
                continue
            index += 1
            extentions.add(ext)
            path = os.path.join(root, f)
            print(path)
            
            with open(path, "rb") as fh:
                tags = exifread.process_file(fh) 
                if not tags:
                    continue
                try:
                    dt = tags['EXIF DateTimeOriginal']
                except KeyError:
                    print(f'{colorama.Fore.YELLOW}{path} does not have DateTimeOriginal!{colorama.Style.RESET_ALL}') 
                    continue
            date, time = str(dt).split()
            name = f"{date.replace(':', '-')}_{time.replace(':', '.')}{ext}"
            new_name = os.path.join(destdir, name)
            if os.path.isfile(new_name):
                print(f'{colorama.Fore.RED}{index}/{count}  {new_name}{colorama.Style.RESET_ALL}')
            else:
                print(f'{index}/{count}  {new_name}')
                shutil.copy2(path, new_name)
            
            
    print(extentions)
            
            
if __name__ == '__main__':
    main()
            