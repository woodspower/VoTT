import os
import glob
import sys, getopt
import re
import json
# use ordereddict to keep key seq of vott file
from collections import OrderedDict
import copy
from shutil import copyfile
import time


# tbd, get the gMaxFrames from video file
gMaxFrames = 2000
gWidth = 1024
gHeight = 768
gFrameTags = []


gBackPath = './backup'



# range format should be a string like '2~5' or '3'
def parse_range(fromto):
    l = re.split('~', fromto)
    if not l:
        return []
    assert len(l)<=2,'Format err:%s'%(fromto)
    # not digit, it is comments field
    if not l[0].isdigit():
        return []
    if len(l)==1:
        # format like '303 '
        f,t = int(l[0]),int(l[0])
    else:
        # format like '303~ 307' or '303~303'
        f,t = int(l[0]),int(l[1])
    assert f<=t, 'Format err:%s'%(fromto)
    return [f,t]


def do_setmap(data, tagmap):
    d = data[u'frames']
    for fromto in tagmap[u'setmap'].keys():
        ids = parse_range(fromto) 
        if not ids:
            continue
        for i in range(ids[0], ids[1]+1):
            fid = str(i)
            assert fid not in d,"%s of %s is duplicate"%(fid, fromto)
            newframe(data, fid, tagmap[u'setmap'][fromto])

def do_copymap(data, tagmap):
    skiped_num = 0
    empty_num = 0
    d = data[u'frames']
    #create a sortable frame copy dict
    idmap = {}
    for fromto in tagmap[u'copymap'].keys():
        ids = parse_range(fromto) 
        if not ids:
            continue
        for i in range(ids[0], ids[1]+1):
            assert i not in idmap,"%s of %s is duplicate"%(fid, fromto)
            idmap[i] = tagmap[u'copymap'][fromto].strip()
    #copy start from the end of frames
    for i in sorted(idmap.keys(), reverse=True):
        tgt = str(i)
        src = idmap[i]
        #do not need copy own
        if tgt is src:
            continue
        if not d.has_key(src) or not d[src]:
            skiped_num+=1
            empty_num+=1
            print("skip frame:%s, since src:%s is empty"%(tgt, src))
            continue
        if d.has_key(tgt):
            skiped_num+=1
            print("skip frame:%s, it already has data"%(tgt))
            continue
        #copy it
        newdata = copy.deepcopy(d[src])
        for box in newdata:
            if box.has_key('mother'):
                if box['mother'] == False:
                    #This box should not be copied
                    newdata.remove(box)
            else:
                #new copied box should not be mother of others
                box['mother'] = False
        if not newdata:
            skiped_num+=1
            empty_num+=1
            print("skip frame:%s, copied frame:%s cannot be mother"%(tgt,src))
            continue
        d[tgt] = newdata
    print("skiped frame num:%d, empty frame num:%d"%(skiped_num, empty_num))
        

def process_mapfile(mapfile, setframe):
    global gMaxFrames
    global gWidth
    global gHeight
    fin = open(mapfile, 'r')
    tagmap = json.loads(fin.read(), object_pairs_hook=OrderedDict)
    gMaxFrames = tagmap['max_frames']
    gWidth = tagmap['width']
    gHeight = tagmap['height']
    fin.close()

    # Input file dir is relative to mapfile
    infile = os.path.join(os.path.dirname(mapfile), tagmap['input'])

    # Backup input file, use mapfile name as subfolder
    backupinput(infile, os.path.basename(mapfile).split('.')[0])

    # Open the input vott tag file
    data = preprocess(infile, setframe)

    if tagmap.has_key('setmap'):
        do_setmap(data, tagmap)

    if tagmap.has_key('copymap'):
        do_copymap(data, tagmap)

    print("data keys:", data[u'frames'].keys())

    # do postprocess
    postprocess(data)

    # Write output file
    # Output file dir is relative to mapfile
    outfile = os.path.join(os.path.dirname(mapfile), tagmap['output'])
    if not os.path.basename(outfile):
        outfile = infile
        print 'Warning... output is same as input', outfile
    fout = open(outfile, 'w')
    fout.write(json.dumps(data, sort_keys=False))
    fout.close()



# Backup the input file
def backupinput(inputfile, subdir):
    path = os.path.join(gBackPath, subdir)
    if not os.path.exists(path):
        os.mkdir(path)
    bakname = os.path.basename(inputfile) + '.tocopy-' + str(int(time.time()))
    copyfile(inputfile, os.path.join(path,bakname))


# Preprocess the vott dict
def preprocess(infile, setframe):
    global gFrameTags
    # Read input file
    fin = open(infile, 'r')
    data = json.loads(fin.read(), object_pairs_hook=OrderedDict)
    fin.close()
    # set global data
    # data["inputTags"] format is "A,B"
    if data[u'inputTags']:
        gFrameTags = data[u'inputTags'].split(', ')
    # del suggestedBy field
    for fid in data[u'frames']:
        frame = data[u'frames'][fid]
        for i in range(len(frame)):
                box = frame[i]
                if box.has_key(u'suggestedBy'):
                        del box[u'suggestedBy']
                if fid == setframe:
                    print 'set frame:%s as mother frame:', setframe
                    if box.has_key('mother'):
                        del box['mother']
    return data

# Postprocess the vott dict
def postprocess(data):
    global gFrameTags
    # set data["inputTags"], format is "A,B"
    # gFrameTags format is ['A','B']
    if gFrameTags:
        data[u'inputTags'] = gFrameTags[0]
        for tag in gFrameTags[1:]:
            data[u'inputTags'] += ',' + tag
    else:
        data[u'inputTags'] = ''
        
    boxid = 1
    data[u'visitedFrames'] = []
    for fid in data[u'frames']:
        # set visited frame to all
        data[u'visitedFrames'].append(int(fid))
        frameboxes = data[u'frames'][fid]
        # NOTICE: vott box name inside each frame must start from 1
        boxname = 1
        for i in range(len(frameboxes)):
                box = frameboxes[i]
                box[u'name'] = boxname
                boxname += 1
                # Add blocksuggest tag, avoid auto copy to next frame
                box[u'blockSuggest'] = True
                # Reallocate id of each dectect box
                if box.has_key(u'id'):
                        box[u'id'] = boxid
                        boxid += 1

# Copy data
# data format
# data is a dict
# data.keys() = [u'scd', u'framerate', u'visitedFrames', u'inputTags', u'frames', u'suggestiontype']
# data[u'frames'] is a dict inside data
# data[u'frames'].keys() = [u'119', u'999', u'120', u'121', u'122', u'123', u'124', u'125', u'118', u'59', u'58', u'55', u'54', u'57', u'56', u'51', u'50', u'53', u'52', u'115', u'114', u'117', u'116', u'111', u'110', u'113', u'112', u'82', u'83', u'80', u'81', u'86', u'87', u'84', u'85', u'108', u'109', u'102', u'103', u'100', u'101', u'106', u'107', u'104', u'105', u'39', u'38', u'37', u'60', u'61', u'62', u'63', u'64', u'65', u'66', u'67', u'68', u'69', u'99', u'98', u'91', u'90', u'93', u'92', u'95', u'94', u'97', u'96', u'88', u'89', u'48', u'49', u'46', u'47', u'44', u'45', u'42', u'43', u'40', u'41', u'1', u'77', u'76', u'75', u'74', u'73', u'72', u'71', u'70', u'79', u'78'] 
# data[u'frames'][u'119'] is a list, each member is a box of dectected object
# data[u'frames'][u'119'][0] is a dict, which describe box rect
# data[u'frames'][u'119'][0] = [u'y2', u'name', u'width', u'tags', u'height', u'x2', u'blockSuggest', u'y1', u'suggestedBy', u'x1', u'type', u'id']
#Here is a full example:
#{
#    "frames": {
#        "1": [
#            {
#                "x1": 1349,
#                "y1": 858,
#                "x2": 1697,
#                "y2": 955,
#                "id": 1,
#                "width": 1697,
#                "height": 955,
#                "type": "Rectangle",
#                "tags": [
#                    "A"
#                ],
#                "name": 1
#            }
#        ]
#    },
#    "framerate": "1",
#    "inputTags": "A,B",
#    "suggestiontype": "copy",
#    "scd": false,
#    "visitedFrames": [
#        1
#    ]
#}
def newframe(data, fid, ftags):
    global gWidth
    global gHeight
    global gFrameTags
    print 'newframe %s: tags:%s'%(fid, ftags) 
    # frame tags may input like: 'Movie,Dialog' or 'Movie Dialog'
    taglist = re.split(' ,', ftags)
    for tag in taglist:
        tag = tag.strip()
        if tag not in gFrameTags:
            gFrameTags.append(tag)
        
    data[u'frames'][fid] = [{'x1':0,\
                             'y1':0,\
                             'x2':gWidth,\
                             'y2':gHeight,\
                             'id':1,\
                             'width':gWidth,\
                             'height':gHeight,\
                             'type':'Rectangle',
                             'tags':taglist,\
                             'name':int(fid) 
                            }]

    
def delframes(data, dframerange):
    global gMaxFrames
    if(dframerange[1] > gMaxFrames):
        dframerange[1] = gMaxFrames
    for fid in range(dframerange[0], dframerange[1]+1):
        key = unicode(str(fid))
        if data[u'frames'].has_key(key):
            del data[u'frames'][key]

def main(argv):
    global gMaxFrames
    mapfile = ''
    mapdir = ''
    setframe = ''
    mapfiles = []

    try:
        opts, args = getopt.getopt(argv, "hf:d:s:",["mapfile=","mapdir=","setframe="])
    except getopt.GetoptError:
        print getopt.GetoptError
        print 'auto_vott.py -m <mapfile> -d <mapdir>'
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            print 'auto_vott.py -m <mapfile> -d <mapdir>'
        elif opt in ("-f", "--mapfile"):
            mapfile = arg
        elif opt in ("-d", "--mapdir"):
            mapdir = arg
        elif opt in ("-s", "--setframe"):
            setframe = arg



    if mapfile:
        print 'If -f exist, only mapfile will be accept', mapfile
        mapfiles = [mapfile]
    else:
        mapfiles = glob.glob(os.path.join(mapdir, '*.map'))
        print '%d *.map files found in %s dir'%(len(mapfiles),mapdir)

    for fname in mapfiles:
        print 'start to process mapfile:', fname
        process_mapfile(fname, setframe)
    





if __name__ == "__main__":
    main(sys.argv[1:])
