############################################################################
#                                                                          #
#                              XMLGEN.PY:                                  #
#                 A script to generate FOXML files for                     #
#               Digital Collections Audio & Video at UMD                   #    
#                      Version 2 -- September 2013                         #  
#                                                                          #
############################################################################
#                                                                          #       
# Recommended command to run this program:                                 #
#                                                                          #       
#     python3 xmlgen2.py 2>&1 | tee xmlgen.log                             #
#                                                                          #       
# (Using this command prints all input and output to screen and also saves #
# it as a log file).                                                       #
#                                                                          #       
# The program assumes that CSV and XML template files are located in the   #
# same directory as the script itself. It also assumes there will be a     #
# subdirectory called output containing another directory called foxml.    #
#                                                                          #       
############################################################################


# Import needed modules
import csv
import datetime
import re
import requests


# Define global variables used as counters and to track summary info
global umdmList
umdmList = []	    # global list for compiling list of UMDM pids
global outputFiles
outputFiles = []    # global list for compiling list of all pids written
global summaryList
summaryList = []    # global list for compiling list of PIDs and Object IDs
global filesWritten
filesWritten = 0    # global counter for file outputs


# Initiates interaction with the program and records the time and user.
def greeting():
    name = input("\nEnter your name: ")
    print("\nHello " + name + ", welcome to the XML generator!")
    currentTime = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    print('It is now ' + str(currentTime))
    print("\nThis program is designed to take data from a CSV file,")
    print("and use that data to generate FOXML files for the")
    print("University of Maryland's digital collections repository.")


# This section analyzes the type of datafile and calculates the number of PIDs needed.
def analyzeDataFile(dataFile):
    dataFileSize = len(dataFile)
    print('\nDoes your datafile contain single or multiple rows for each object?')
    dataFileArrangement = input('Please enter S or M: ')
    while dataFileArrangement not in ('S','M'):
        dataFileArrangement = input('Please enter either S for sigle-rowed data, or M for multi-rowed data: ')
    print('\nThe datafile you specified has {0} rows.'.format(dataFileSize))
    if dataFileArrangement == 'S':
        print('Since you have single-rowed objects, you need two PIDs for each row.')
        dataLength = (dataFileSize - 1) * 2
    elif dataFileArrangement == 'M':
        print('Since you have multi-rowed objects, you need one PID for each row.')
        dataLength = dataFileSize - 1
    print('Assuming there is a header row in your datafile, you need {0} PIDs.'.format(dataLength))
    print('Load {0} PIDs from a file or request them from the server?'.format(dataLength))
    return dataLength, dataFileArrangement


# Reads the length of the CSV datafile and guides user in requesting
# necessary number of PIDs from either the stage (for testing) or production server
def getPids(dataLength):
    pidList = []
    pidSource = input('Enter F (file) or S (server): ')
    while (pidSource not in ('F','S')):
        print("ERROR: you must enter either 'F' to load PIDs from a file, or 'S' to request them from the server!")
        pidSource = input('Please try again: ')
    if pidSource == 'F':
        pidFileName = input('Enter the name of the PID file: ')
        pidFile = open(pidFileName, 'r').read()
    elif pidSource == 'S':
        pidFile = requestPids(dataLength)   # Requests as many PIDs as lines of data.
    return pidFile


# This function handles the request for PIDs from the server, 
# requesting a specified number of PIDs and saving the resulting XML file.
def requestPids(numPids):                   
    serverChoice = input('Enter S to get PIDs on fedoraStage, P to get PIDs on Production: ')
    while (serverChoice not in ('S', 'P')): # Choose the production or stage server
        serverChoice = input('Error: You must enter S or P: ')
    if serverChoice == 'S':
        url = 'http://fedorastage.lib.umd.edu/fedora/management/getNextPID?numPids='
    elif serverChoice == 'P':
        url = 'http://fedora.lib.umd.edu/fedora/management/getNextPID?numPids='
    url += '{0}&namespace=umd&xml=true'.format(numPids)
    username = input('\nEnter the server username: ')          # prompts user for auth info
    password = input('Enter the server password: ')
    f = requests.get(url, auth=(username, password)).text      # submits request to fedora server
    print("\nRetrieving PIDs from the server...")
    print('\nServer answered with the following XML file:\n')  # print server's response
    print(f)
    fName = input('Enter a name under which to save the server\'s PID file: ')
    writeFile(fName, f, '.txt')
    return f


# Takes the XML-based PID file provided by Fedora, and parses it to retrieve just the pids,
# loading them into a Python list and returning it.
def parsePids(pidFile):
    pidList = []                                            # create list to hold PIDs
    for line in pidFile.splitlines():                       # for each line in the response
        pid = re.search('<pid>(.*?)</pid>', line)           # search for PID and if found
        if pid:
            pidList.append(pid.group(1))                    # append each PID to list
    resultLength = str(len(pidList))
    print('\nSuccessfully loaded the following {0} PIDs: '.format(resultLength))
    print(pidList)
    return pidList


# Generates the specific XML tags based on dating information stored in the myDate dictionary
# previously returned by the parseDate function.
def generateDateTag(inputDate, inputAttribute):
    dateTagList = []
    myDate = parseDate(inputDate, inputAttribute)
    if myDate['Type'] == 'range':
        elements = myDate['Value'].split('-')   # split the date into its parts
        if len(elements) == 2:                  # if there are two parts, use those as begin/end years
            beginDate = elements[0]
            endDate = elements[1]
        elif len(elements) == 6:                # if there are 6 parts, use index 0 and 4 as begin/end years
            beginDate = elements[0]             # i.e. we assume YYYY-MM-DD-YYYY-MM-DD format for exact date ranges
            endDate = elements[4]
        myTag = '<date certainty="{0}" era="ad" from="{1}" to="{2}">{3}</date>'.format(myDate['Certainty'], beginDate, endDate, myDate['Value'])
        dateTagList.append(myTag)
    elif myDate['Number'] == 'multiple':
        for i in myDate['Value']:
            myTag = '<date certainty="{0}" era="ad">{1}</date>'.format(myDate['Certainty'], i.strip())
            dateTagList.append(myTag)
    else:
        myTag = '<date certainty="{0}" era="ad">{1}</date>'.format(myDate['Certainty'], myDate['Value'])
        dateTagList.append(myTag)
    return '\n'.join(dateTagList)


# This function parses the date attributes stored in a particular column of the input data.
def parseDate(inputDate, inputAttribute):
    myDate = {}
    if 'multiple' in inputAttribute:            # multiple or single date?
        myDate['Number'] = 'multiple'
    else:
        myDate['Number'] = 'single'
    if 'circa' in inputAttribute:               # exact or circa?
        myDate['Certainty'] = 'circa'
    else:
        myDate['Certainty'] = 'exact'
    if 'range' in inputAttribute:               # range or point?  
        myDate['Type'] = 'range'
    else:
        myDate['Type'] = 'date'
    if myDate['Number'] == 'multiple':          # set value --> split if multiple, otherwise single value
        myDate['Value'] = inputDate.split(';')
    else:
        myDate['Value'] = inputDate
    return myDate


# Prompts the user to enter the name of the UMAM or UMDM template or PID file and
# read that file, returning the contents.
def loadFile(fileType):
    sourceFile = input("\nEnter the name of the %s file: " % (fileType))
    if fileType == 'data':
        f = open(sourceFile, 'r').readlines()
    else:
        f = open(sourceFile, 'r').read()
    return(f, sourceFile)


# Creates a file containing the contents of the "content" string, named umd_[PID].xml,
# with all files saved in dir 'output', and XML files in the sub-dir 'foxml'.
def writeFile(fileStem, content, extension):
    if extension == '.xml':
        filePath = 'output/foxml/' + fileStem + extension
    else:
        filePath = 'output/' + fileStem + extension
    f = open(filePath, mode='w')
    f.write(content)
    f.close()


# When passed a string in the format 'HH:MM:SS', returns the decimal value in minutes,
# rounded to two decimal places.
def convertTime(inputTime):
    if inputTime == "":                 # if the input string is empty, return the same string
        return inputTime
    hrsMinSec = inputTime.split(':')    # otherwise, split the string at the colon
    minutes = int(hrsMinSec[0]) * 60    # multiply the first value by 60
    minutes += int(hrsMinSec[1])        # add the second value
    minutes += int(hrsMinSec[2]) / 60   # add the third value divided by 60
    print('Time Conversion: ' + str(hrsMinSec) + ' = ' + str(round(minutes, 2))) # print result
    return round(minutes, 2)            # return the resulting decimal rounded to two places


# Performs series of find and replace operations to generate UMAM file from the template.
def createUMAM(data, template):
    
    timeStamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    convertedRunTime = convertTime(data['TotalRunTimeDerivatives'])
    
    # initialize the output starting with the specified template file
    outputfile = template
    
    # create mapping of the metadata onto the UMAM XML template file
    umamMap = {'!!!PID!!!' : data['PID'],
               '!!!Title!!!' : data['Title'],
               '!!!DigitizationNotes!!!' : data['Digitization Notes'],
               '!!!FileName!!!' : data['File Name'],
               '!!!Mono/Stereo!!!' : data['Mono/Stereo'],
               '!!!Sharestream!!!' : data['ShareStreamURLs'],
               '!!!TrackFormat!!!' : data['Track Format'],
               '!!!DateDigitized!!!' : data['DateDigitized'],
               '!!!DigitizedByPers!!!' : data['DigitizedByPers'],
               '!!!TotalRunTimeDerivatives!!!' : str(convertedRunTime) }
    
    # Carry out a find and replace for each line of the data mapping
    for anchor in umamMap:
        outputfile.replace(anchor, umamMap[anchor])
    
    return outputfile, convertedRunTime


# Performs series of find and replace operations to generate UMDM file from the template.
def populateUMDM(data, template, summedRunTime):
    timeStamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    outputfile = template.replace('!!!PID!!!', data['PID'])
    outputfile = outputfile.replace('!!!Title!!!', data['Title'])
    outputfile = outputfile.replace('!!!AlternateTitle!!!', data['Alternate Title'])
    outputfile = outputfile.replace('!!!Contributor!!!', data['Contributor'])
    outputfile = outputfile.replace('!!!ItemControlNumber!!!', data['Item Control Number'])
    outputfile = outputfile.replace('!!!Description/Summary!!!', data['Description/Summary'])
    outputfile = outputfile.replace('!!!CopyrightHolder!!!', data['Copyright Holder'])
    outputfile = outputfile.replace('!!!Continent!!!', data['Continent'])
    outputfile = outputfile.replace('!!!Country!!!', data['Country'])
    outputfile = outputfile.replace('!!!Region/State!!!', data['Region/State'])
    outputfile = outputfile.replace('!!!Settlement/City!!!', data['Settlement/City'])
    outputfile = outputfile.replace('!!!DateAnalogCreated!!!', data['DateAnalogCreated'])
    dateTagString = generateDateTag(data['DateAnalogCreated'], data['CreatedDateCertainty'])
    outputfile = outputfile.replace('!!!InsertDateHere!!!', dateTagString)
    outputfile = outputfile.replace('!!!Repository!!!', data['Repository'])
    if data['SizeReel'].endswith('"'):
        data['SizeReel'] = data['SizeReel'][0:-1]
    outputfile = outputfile.replace('!!!SizeReel!!!', data['SizeReel'])
    runTimeMasters = str(round(summedRunTime, 2))
    outputfile = outputfile.replace('!!!TotalRunTimeMasters!!!', runTimeMasters)
    outputfile = outputfile.replace('!!!TypeOfMaterial!!!', data['TypeofMaterial'])
    outputfile = outputfile.replace('!!!Collection!!!', data['Collection'])
    outputfile = outputfile.replace('!!!BoxNumber!!!', data['Box Number'])
    outputfile = outputfile.replace('!!!AccessionNumber!!!', data['Accession Number'])
    outputfile = outputfile.replace('!!!TimeStamp!!!', timeStamp)
    return outputfile


def createUMDM(data, umdm, summedRunTime, mets, objectParts):
    global outputFiles
    global umdmList
    global filesWritten

    # Create the UMDM
    timeStamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    myFile = populateUMDM(data, umdm, summedRunTime)        # Populate the UMDM
    myFile = myFile.replace('!!!INSERT_METS_HERE!!!', mets) # Insert the METS
    myFile = stripAnchors(myFile)                           # Strip out anchor points
    myFile = myFile.replace('!!!TimeStamp!!!', timeStamp)   # Apply the timestamp
    fileStem = data['PID'].replace(':', '_').strip()        # convert ':' to '_' in PID for use in filename
    writeFile(fileStem, myFile, '.xml')                     # Write the file
    
    # Print summary info to the screen
    print('Creating UMDM for object with {0} parts...'.format(objectParts), end=" ")
    print('\nTotal runtime of all parts = {0}.'.format(str(summedRunTime)))
    print('UMDM = {0}'.format(fileStem))
    
    # Append PID to list of all files created and list of UMDM files created
    umdmList.append(data['PID'])
    outputFiles.append(data['PID'])
    filesWritten += 1


# Initiates a METS section for use in a UMDM file
def createMets():
    metsFile = open('mets.xml', 'r').read()
    return(metsFile)


# Updates a METS record with UMAM info
def updateMets(partNumber, mets, fileName, pid):
    id = str(partNumber + 2)   # first part is file 3 because the first two files are the collection PIDs for AlbUM and WMUC
    metsSnipA = open('metsA.xml', 'r').read() + '!!!Anchor-A!!!'
    metsSnipB = open('metsB.xml', 'r').read() + '!!!Anchor-B!!!'
    metsSnipC = open('metsC.xml', 'r').read() + '!!!Anchor-C!!!'
    mets = mets.replace('!!!Anchor-A!!!', metsSnipA)
    mets = mets.replace('!!!Anchor-B!!!', metsSnipB)
    mets = mets.replace('!!!Anchor-C!!!', metsSnipC)
    mets = mets.replace('!!!FileName!!!', fileName)
    mets = mets.replace('!!!ID!!!', id)
    mets = mets.replace('!!!PID!!!', pid)
    mets = mets.replace('!!!Order!!!', str(partNumber))
    return mets


# Strips out the anchor points used in creating the METS 
def stripAnchors(target):
    f = re.sub(r"\n\s*!!!Anchor-[ABC]!!!", "", target)
    return f


def main():
    
    # Initialize needed variables and lists
    
    mets = ""		        # empty string for compiling METS record
    objectGroups = 0            # counter for UMDM plus UMAM(s) as a group
    objectParts = 0             # counter for the number of UMAM parts for each UMDM
    summedRunTime = 0           # variable to hold sum of constituent UMAM runtimes for UMDM
    pidCounter = 0              # counter for coordinating PID list with data lines from CSV
    global filesWritten
    
    # Create a timeStamp for these operations
    timeStamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    # Initiate the program, recording the timestamp and name of user
    greeting()
    
    # Load CSV data
    dataFile, fileName = loadFile('data')
    
    # Parse loaded data and request user input to calculate num of PIDS needed
    pidsNeeded, dataFileArrangement = analyzeDataFile(dataFile)
    
    # Request PIDs from the server OR load PIDs from previously saved file.
    pidFile = getPids(pidsNeeded)
    
    # Parse the XML PID file (either local or from the server) to get list of PIDs
    pidList = parsePids(pidFile)
    
    # Check whether the loaded file has enough PIDs, abort if not enough
    if len(pidList) < pidsNeeded:
        print('Not enough PIDs for your dataset!')
        print('Please reserve additional PIDs from the server and try again.')
        print('Exiting program.')
        quit()
    
    # Load the UMAM template and print it to screen  
    umam, umamName = loadFile('UMAM')
    print("\n UMAM:\n" + umam)
    print('*' * 30)
    
    # Load the UMDM template and print it to screen
    umdm, umdmName = loadFile('UMDM')
    print("\n UMDM:\n" + umdm)
    print('*' * 30)
    
    # Load the lines of the data file into a csv.DictReader object
    myData = csv.DictReader(dataFile)
    print('Data successfully read.')
    
    # Generate XML for data arranged with multiple lines (UMAM and UMDM) per object
    if dataFileArrangement == 'M':
        
        for x in myData:
            # Attach a PID to the line of data.
            x['PID'] = pidList[pidCounter]
            pidCounter += 1
            
            # Attach summary info to summary list, depending on XML type
            if x['XML Type'] == 'UMDM':
                link = '"{0}","{1}","{2}","http://digital.lib.umd.edu/video?pid={2}"'.format(x['Item Control Number'], x['XML Type'], x['PID'])
            elif x['XML Type'] == 'UMAM':
                link = '"{0}","{1}","{2}"'.format(x['Item Control Number'], x['XML Type'], x['PID'])
            summaryList.append(link)
            
            # Check the XML type for each line, and build the FOXML files accordingly
            if x['XML Type'] == 'UMDM':
                
                # If the mets variable is NOT empty, finish the UMDM for the previous group
                if mets != "":
                    createUMDM(tempData, umdm, summedRunTime, mets, objectParts)
                    
                    # Reset counters
                    objectParts = 0     # reset parts counter
                    summedRunTime = 0   # reset runtime sum counter
                
                # Begin a new UMDM group by incrementing the group counter, printing a notice to screen,
                # storing the line of UMDM data for use after UMAMs are complete, and initiating a new METS
                objectGroups += 1
                print('\nFILE GROUP {0}: '.format(objectGroups))
                tempData = x
                mets = createMets()
                
            # If the line is a UMAM line
            elif x['XML Type'] == 'UMAM':
                
                # Print summary info to the screen
                print('Writing UMAM...', end=' ')
                
                # Create UMAM, convert PID for use as filename, write the file
                myFile, convertedRunTime = createUMAM(x, umam)
                fileStem = x['PID'].replace(':', '_').strip()
                print('Part {0}: UMAM = {1}'.format(objectParts, fileStem))
                writeFile(fileStem, myFile, '.xml')
                
                # Increment counters
                summedRunTime += convertedRunTime
                objectParts += 1
                filesWritten += 1
                
                # Update the running METS record for use in finishing the UMDM
                mets = updateMets(objectParts, mets, x['File Name'], x['PID'])
                
        # After iteration complete, finish the last UMDM    
        createUMDM(tempData, umdm, summedRunTime, mets, objectParts)
        
    # Generate XML for data arranged with single lines (UMAM plus UMDM) per object
    elif dataFileArrangement == 'S':
        
        # Assign two PIDs to each line
        for x in myData:
            x['umdmPID'] = pidList[pidCounter]
            pidCounter += 1
            x['umamPID'] = pidList[pidCounter]
            pidCounter += 1
            
            # Attach summary info to summary list, once for each file
            link1 = '"{0}","{1}","{2}","http://digital.lib.umd.edu/video?pid={2}"'.format(x['Item Control Number'], 'UMDM', x['umdmPID'])
            link2 = '"{0}","{1}","{2}"'.format(x['Item Control Number'], 'UMAM', x['umamPID'])
            summaryList.append(link1)
            summaryList.append(link2)
            
            # Increment the object counter and print feedback to screen
            objectGroups += 1
            print('\nFILE GROUP {0}: '.format(objectGroups))
            
            # Initiate the METS
            mets = createMets()
            
            # Create UMAM, convert PID for use as filename, write the file
            x['PID'] = x['umamPID']
            myFile, convertedRunTime = createUMAM(x, umam)
            fileStem = x['umamPID'].replace(':', '_').strip()
            writeFile(fileStem, myFile, '.xml')
            
            # Increment counters
            summedRunTime += convertedRunTime
            objectParts += 1
            filesWritten += 1
            
            # Update the running METS record for use in finishing the UMDM
            mets = updateMets(objectParts, mets, x['File Name'], x['umamPID'])
            
            # Print summary info to the screen
            print('Part {0}: UMAM = {1}'.format(objectParts, fileStem))
            print('Writing UMAM...', end=' ')
            
            # Create UMDM
            x['PID'] = x['umdmPID']
            createUMDM(x, umdm, summedRunTime)
                    
            # Reset counters
            objectParts = 0     # reset parts counter
            summedRunTime = 0   # reset runtime sum counter
        
    # Abort if the value of dataFileArrangement is something else
    else:
        print('Bad dataFileArrangement value!')
        quit()
        
    # Generate summary files
    print('\nWriting pidlist file as pids.txt...')
    f = '\n'.join(outputFiles)
    writeFile('pids', f, '.txt')
    filesWritten += 1
    
    print('Writing summary file as links.txt...')
    l = '\n'.join(summaryList)
    writeFile('links', l, '.txt')
    filesWritten += 1
    
    print('Writing list of UMDM files as UMDMpids.txt...')
    d = '\n'.join(umdmList)
    writeFile('UMDMpids', d, '.txt')
    filesWritten += 1
    
    # Print a divider and summarize output to the screen.
    print('\n' + ('*' * 30))               
    print('\n{0} files written: {1} FOXML files in {2}'.format(filesWritten, filesWritten - 3, objectGroups), end=' ')
    print('groups, plus the summary list of pids, list of UMDM pids, and the links file.')
    print('Thanks for using the XML generator!\n\n')
        
main()
