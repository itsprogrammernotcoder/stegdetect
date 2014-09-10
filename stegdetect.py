# This script scans for images that have data appended to them
# and copies the images and the appended data to the folder appended-file-scanner-discoveries
# with log at appended-file-scanner-log.txt
#
# Download from http://pastebin.com/raw.php?i=L3V9HxFh
# and save as scanner.py
#
# You can simply save it to the folder you want to scan and run it.
#
# To scan specific files/folders, drag them to the script, or type
#   scanner.py files-or-folders-to-scan
# at the command line.
#
# You need to have Python installed for this to work -- available from http://python.org/
# Either Python 2.3+ or Python 3.* should work.

import sys, os, shutil, struct, traceback
if sys.version_info[0] < 3:
    ascii = repr
    input = raw_input

def color_table_length(c):
    """Read the flags in a GIF file to get the length of the color table."""
    if c & 0x80:
        return 3 << ((c & 0x07) + 1)
    else:
        return 0

def end_of_blocks(data, start):
    """Find the end of a sequence of GIF data sub-blocks."""
    i = start
    while i < len(data):
        if data[i] == 0:
            return i + 1
        else:
            i += data[i] + 1
    return len(data)

def gif_end(data):
    """Find the end of GIF data in a file."""
    if type(data) == str:
        data2 = [ord(c) for c in data]
    else:
        data2 = data
    if len(data) <= 10:
        return len(data)
    i = color_table_length(data2[10]) + 13
    while i < len(data):
        if data2[i] == 0x2c:
            i += 9
            if i >= len(data):
                return len(data)
            i += color_table_length(data2[i]) + 2
            i = end_of_blocks(data2, i)
        elif data2[i] == 0x21:
            i = end_of_blocks(data2, i+2)
        elif data2[i] == 0x3b:
            return i + 1
        else:
            return i
    return min(i, len(data))

def jpg_end(data):
    """Find the end of JPEG data in a file."""
    if type(data) == str:
        data2 = [ord(c) for c in data]
    else:
        data2 = data
    i = 2
    while i + 2 <= len(data):
        if data2[i] == 0xff and data2[i+1] >= 0xc0:
            if data2[i+1] == 0xd9:
                return i + 2
            elif data2[i+1] == 0xd8:
                return i
            elif 0xd0 <= data2[i+1] <= 0xd7:
                i += 2
            else:
                if i + 4 > len(data):
                    return len(data)
                i += struct.unpack('>H', data[i+2:i+4])[0] + 2
        else:
            i += 1
    return min(i, len(data))

def png_end(data):
    """Find the end of PNG data in a file."""
    i = 8
    while i + 8 < len(data):
        length, chunk_type = struct.unpack('>LL', data[i:i+8])
        if chunk_type == 1229278788: # IEND
            return min(i + 12, len(data))
        i += length + 12
    return min(i, len(data))

def image_end(data):
    """Find the end of the image data in a file."""
    magic = data[:8]
    if type(magic) != str:
        magic = magic.decode('latin_1')
    if magic.startswith('GIF87a') or magic.startswith('GIF89a'):
        return gif_end(data)
    elif magic.startswith('\xFF\xD8'):
        return jpg_end(data)
    elif magic.startswith('\x89PNG\x0D\x0A\x1A\x0A'):
        return png_end(data)
    else:
        return len(data) # Report no appended data for non-images

def scan(fullname, outpath, logwrite):
    """
    Scan file named fullname for appended content.  If found:
      copy file and appended content to outpath
      report details to logwrite function
      return True
    """
    f = open(fullname, 'rb')
    try:
        data = f.read()
    finally:
        f.close()
    eoi = image_end(data)
    if eoi == len(data):
        return False
    logwrite(fullname)
    logwrite('found %d bytes starting with:' % (len(data) - eoi))
    logwrite(ascii(data[eoi:eoi+20]))
    outputbasename = os.path.basename(fullname)
    outputname = os.path.join(outpath, outputbasename)
    extractname = os.path.join(outpath, outputbasename + '.data')
    if os.path.realpath(outputname) != fullname:
        nrename = 1
        while os.path.exists(outputname) or os.path.exists(extractname):
            nrename += 1
            outputbasename = 'File %d named ' % nrename + os.path.basename(fullname)
            outputname = os.path.join(outpath, outputbasename)
            extractname = os.path.join(outpath, outputbasename + '.data')
    if not os.path.exists(outputname):
        shutil.copy(fullname, outputname)
        logwrite('copied to ' + outputbasename)
    if not os.path.exists(extractname):
        extractf = open(extractname, 'wb')
        try:
            extractf.write(data[eoi:])
        finally:
            extractf.close()
    logwrite('')
    return True

logfile = None
try:
    # Create output directory, log
    LOGNAME = 'appended-file-scanner-log.txt'
    OUTDIRNAME = 'appended-file-scanner-discoveries'
    scriptdir = os.path.dirname(os.path.realpath(__file__))
    logfullname = os.path.join(scriptdir, LOGNAME)
    outpath = os.path.join(scriptdir, OUTDIRNAME)
    try:
        os.mkdir(outpath)
    except OSError:
        pass
    logfile = open(logfullname, 'a+')
    def logwrite(line):
        line = ''.join([c for c in line if ' ' <= c <= '~' or c in '\t\n'])
        print(line)
        logfile.write(line + '\n')

    # Enumerate files to scan
    targets = [os.path.realpath(name) for name in sys.argv[1:]]
    if len(targets) == 0:
        targets = [scriptdir]
    logwrite('scanning')
    logwrite('\n'.join(targets))
    logwrite('')
    scanlist = []
    for target in targets:
        if os.path.isdir(target):
            for root, dirs, files in os.walk(target):
                for file in files:
                    if file.lower().split('.')[-1] in ('gif', 'jpg', 'jpeg', 'png'):
                        scanlist.append(os.path.join(root, file))
        else:
            scanlist.append(target)

    # Scan files
    anyfound = False
    for fullname in scanlist:
        try:
            datafound = scan(fullname, outpath, logwrite)
            if datafound:
                anyfound = True
        except:
            traceback.print_exc()
            traceback.print_exc(logfile)
    if not anyfound:
        logwrite('no files found\n')

    logfile.close()
except:
    traceback.print_exc()
    if logfile != None:
        logfile.close()

print('[press return]')
input()
