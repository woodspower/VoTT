import os
import sys, getopt
import re
import json
# use ordereddict to keep key seq of vott file
from collections import OrderedDict
import copy
from shutil import copyfile
import time


# tbd, get the totalframes from video file
totalframenum = 2000



bakpath = './backup'


copylist = [
    {'name': 'majorgui', 'base': '344', 
     'copyto': ['450~450' 
               ]
    },
    {'name': 'dialoggui_ask', 'base': '108', 
     'copyto': ['451~451'
               ]
    },
    {'name': 'dialoggui_ok', 'base': '109', 
     'copyto': ['452~452',
               ]
    }

#{'name': 'majorgui', 'base': 344, 
# 'copyto': ['292~302',
#            '308~315',
#            '321',
#            '324',
#            '330~337',
#            '344~359',
#            '363~383']}
#,
#{'name': 'dialoggui_ask', 'base': 108, 
# 'copyto': ['303~305',
#            '316~320',
#            '325~329',
#            '338~341',
#            '360~361',
#            '384~386']}
#,
#{'name': 'dialoggui_ok', 'base': 109, 
# 'copyto': ['306~307',
#            '322~323',
#            '342~343',
#            '362',
#            '387']}
#,
#{'name': 'animategui', 'base': 34, 
# 'copyto': ['316~317']}
]


fidlist = []
def checkcopylist(copylist):
    global fidlist
    for batch in copylist:
        fidlist.append(int(batch['base']))
        for tolist in batch['copyto']:
            fromto = tolist.split('~')
            if(len(fromto) == 1):
                fromto.append(fromto[0])
            assert(len(fromto) == 2)
            print("fromto is:", fromto, fromto[0], fromto[1])
            for fid in range(int(fromto[0]), int(fromto[1])+1):
                assert fid not in fidlist , "%d of %s is duplicate"%(fid, batch['name'])
                fidlist.append(fid)
    fidlist.sort()
    print fidlist
    

def batchcopy(data, copylist):
    checkcopylist(copylist)
    for batch in copylist:
        for tolist in batch['copyto']:
            fromto = tolist.split('~')
            if(len(fromto) == 1):
                fromto.append(fromto[0])
            assert(len(fromto) == 2)
            copyframes(data, int(batch['base']), [int(fromto[0]),int(fromto[1])])

# Backup the input file
def backupinput(inputfile):
    #bakname = os.path.basename(inputfile) + '.tocopy-' + str(fidlist[0]) + '-' + str(fidlist[-1])
    bakname = os.path.basename(inputfile) + '.tocopy-' + str(int(time.time()))
    copyfile(inputfile, os.path.join(bakpath,bakname))


# Preprocess the vott dict
def preprocess(data):
    # del suggestedBy field
    for fid in data[u'frames']:
        frame = data[u'frames'][fid]
        for i in range(len(frame)):
                box = frame[i]
                if box.has_key(u'suggestedBy'):
                        del box[u'suggestedBy']

# Postprocess the vott dict
def postprocess(data):
    boxid = 0
    for fid in data[u'frames']:
        frame = data[u'frames'][fid]
        for i in range(len(frame)):
                box = frame[i]
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
def copyframes(data, cframesrc, cframerange):
    print 'copyframes from %d to %d-%d'%(cframesrc, cframerange[0], cframerange[1])
    datasrc = data[u'frames'][unicode(str(cframesrc))]
    if(cframerange[1] > totalframenum):
        cframerange[1] = totalframenum
    for fid in range(cframerange[0], cframerange[1]+1):
        newdata = copy.deepcopy(datasrc)
        data[u'frames'][unicode(str(fid))] = newdata
    
def delframes(data, dframerange):
    if(dframerange[1] > totalframenum):
        dframerange[1] = totalframenum
    for fid in range(dframerange[0], dframerange[1]+1):
        key = unicode(str(fid))
        if data[u'frames'].has_key(key):
            del data[u'frames'][key]

def main(argv):
    global totalframes
    infile = ''
    outfile = ''
    needtocopy = False
    needbatchcopy = False
    needtodel = False
    cframesrc = 0
    cframerange = [0, 0]
    dframerange = [0, 0]

    try:
        opts, args = getopt.getopt(argv, "hi:o:d:c:b:",["infile=", "outfile=", "del=", "copy=", "batchcopy="])
    except getopt.GetoptError:
        print getopt.GetoptError
        print 'vottcopy.py -i <inputfile> -o <outputfile> -c <copyframes> -d <deleteframes> -b <batchcopyconf>'
        print 'or: vottcopy.py --infile=<inputfile> --outfile=<outputfile> --copy=<copyframes> --del=<delframes>'
        print("--copy '46 47' means copy frame 46 to frame 47")
        print("--copy '46 47~100' means copy frame 46 to frame 47,48,...,100")
        print("--copy '46 ~100' means copy frame 46 to frame 47,48,...,100")
        print("--copy '46 90~' means copy frame 46 to frame 90,91,...till end of frames")
        print("--copy '46 ~' means copy frame 46 to frame 47,48,...till end of frames")

        print("--delete '47' means delete frame 47")
        print("--delete '47~100' means delete frame 47,48,...,100")
        print("--delete '90~' means delete frame 90,91,...till end of frames")

        print 'or: vottcopy.py --batchcopy=<batchcopyconf>'
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            print 'vottcopy.py -i <inputfile> -o <outputfile> -c <copyframes> -d <deleteframes>'
            print 'or: vottcopy.py --infile=<inputfile> --outfile=<outputfile> --copy=<copyframes> --del=<delframes>'
            print("--copy '46 47' means copy frame 46 to frame 47")
            print("--copy '46 47~100' means copy frame 46 to frame 47,48,...,100")
            print("--copy '46 ~100' means copy frame 46 to frame 47,48,...,100")
            print("--copy '46 90~' means copy frame 46 to frame 90,91,...till end of frames")
            print("--copy '46 ~' means copy frame 46 to frame 47,48,...till end of frames")

            print("--delete '47' means delete frame 47")
            print("--delete '47~100' means delete frame 47,48,...,100")
            print("--delete '90~' means delete frame 90,91,...till end of frames")

            print 'or: vottcopy.py --batchcopy=<batchcopyconf>'
            sys.exit()
        elif opt in ("-b", "--batchcopy"):
            needbatchcopy = True
            needtocopy = False
            needtodel = False
            break
        elif opt in ("-i", "--infile"):
            infile = arg
        elif opt in ("-o", "--outfile"):
            outfile = arg
        elif opt in ("-c", "--copy"):
            needtocopy = True
            arg = re.split(' ', arg)
            # find where copy from
            assert(len(arg)==2)
            cframesrc = int(arg[0])
            # find where copy to
            startend = re.split('~', arg[1])
            # print("startend is:", startend)
            assert(len(startend)==2 or len(startend)==1)
            if(len(startend) == 2):
                if(startend[0] == ''):
                    start = cframesrc + 1
                else:
                    start = int(startend[0])
                if(startend[1] == ''):
                    end = 0x7FFFFFF
                else:
                    end = int(startend[1])
                cframerange = [start, end]
            else:
                if(startend[0] == ''):
                    start = cframesrc + 1
                else:
                    start = int(startend[0])
                cframerange = [start, start]
        elif opt in ("-d", "--delete"):
            needtodel = True
            # find where to del
            startend = re.split('~', arg)
            # print("startend is:", startend)
            assert(len(startend)==2 or len(startend)==1)
            assert(startend[0] != '')
            start = int(startend[0])
            if(len(startend) == 2):
                if(startend[1] == ''):
                    end = 0x7FFFFFF
                else:
                    end = int(startend[1])
                dframerange = [start, end]
            else:
                dframerange = [start, start]
                
            
            


    if not infile:
        print 'please input a file'
        return

    if not outfile:
        outfile = infile

    print 'Input file : ', infile
    print 'Output file: ', outfile

    # Backup input file
    backupinput(infile)

    # Read input file
    fin = open(infile, 'r')
    data = json.loads(fin.read(), object_pairs_hook=OrderedDict)

    # do preprocess
    preprocess(data)

    # Start Batch copy
    if(needbatchcopy):
        print 'Start batch copy list:', copylist
        batchcopy(data, copylist)

    # Start to copy
    if(needtocopy):
        print 'Start to copy from %d to %d-%d'%(cframesrc, cframerange[0], cframerange[1])
        # cframerange.start should less than end
        assert(cframerange[0] <= cframerange[1])
        delframes(data, cframerange)
        copyframes(data, cframesrc, cframerange)
    
    # Start to del
    if(needtodel):
        print 'Start to del from %d-%d'%(dframerange[0], dframerange[1])
        # dframerange.start should less than end
        assert(dframerange[0] <= dframerange[1])
        delframes(data, dframerange)


    print("data keys:", data[u'frames'].keys())

    # do postprocess
    postprocess(data)

    # Write output file
    fout = open(outfile, 'w')
    fout.write(json.dumps(data, sort_keys=False))
    fout.close()


if __name__ == "__main__":
    main(sys.argv[1:])
