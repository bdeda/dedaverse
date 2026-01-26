# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################

import sys
import os
import platform
from pathlib import Path

# Conditional debugger import (only on Windows and when WING_DEBUG env var is set)
if platform.system() == 'Windows' and os.getenv('WING_DEBUG'):
    try:
        wing_path = Path(r'C:\Program Files\Wing Pro 10')
        if wing_path.exists():
            sys.path.insert(0, str(wing_path))
            import wingdbstub
    except ImportError:
        pass
    finally:
        if sys.path and sys.path[0] == str(wing_path):
            sys.path = sys.path[1:]

import exifread
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
            path = Path(root) / f
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
            new_name = Path(destdir) / name
            if new_name.is_file():
                print(f'{colorama.Fore.RED}{index}/{count}  {new_name}{colorama.Style.RESET_ALL}')
            else:
                print(f'{index}/{count}  {new_name}')
                shutil.copy2(path, new_name)
            
            
    print(extentions)
            
            
if __name__ == '__main__':
    main()
            