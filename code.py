# SPDX-FileCopyrightText: 2021 Sandy Macdonald
#
# SPDX-License-Identifier: MIT

# This example demonstrates how to light keys when pressed.

# Drop the `pmk` folder
# into your `lib` folder on your `CIRCUITPY` drive.


# connctions
# 40->1  (power to 1st pin of display)
# 36->6*_>15  (3.3v to 6th* pin of display, to first pin analog keypad)
# 31->17  (ADC0 to 3rd pin (output of analog keypad))
# 23_>16 (GND to 2nd pin (GND of analog keypad)) - but could use 38 of pi pico
# 
# 
# 
# 
# 18->7 (GND PI TO GND display)
# 17->2 (Chip Select to CS)
# 14->3 (SCK to SCK)
# 15->4 (MOSI)
# 16_>5 (DC)
# see * above
# 
# 
# tft_cs = board.GP13
# tft_dc = board.GP12
# spi_mosi = board.GP11
# spi_clk = board.GP10
################################################

#########NOTES FOR MPC3008###############
#pins on mpc with connections
# 16->3v
# 15->3v
# 14->GND
# 13 SCK   (sck to clk) GP02
# 12 DOUT  (to miso)    GP04
# 11 DIN	 (to mosi)    GP03
# 10 CS    (            GP05
# 9->GND
# # create the spi bus
# spi = busio.SPI(clock=GP02, MISO=GP04, MOSI=board.GP03)
# # create the cs (chip select)
# cs = digitalio.DigitalInOut(board.GP05)
# # create the mcp object
# mcp = MCP.MCP3008(spi, cs)
#might try different mux however
#########################################


import board
import digitalio
import busio

import terminalio
import displayio
from adafruit_display_text import label, wrap_text_to_lines
from adafruit_st7789 import ST7789

from adafruit_datetime import datetime
from analogio import AnalogIn
import time
from pmk import PMK
#from pmk.platform.keybow2040 import Keybow2040 as Hardware          # for Keybow 2040
from pmk.platform.rgbkeypadbase import RGBKeypadBase as Hardware  # for Pico RGB Keypad Base

import usb_midi
import adafruit_midi
from adafruit_midi.note_off import NoteOff
from adafruit_midi.note_on import NoteOn
from adafruit_midi.control_change import ControlChange
from adafruit_midi.program_change import ProgramChange

keybow = PMK(Hardware())
keys = keybow.keys

drumNotesPlayed = []

debugging=False

#spi = busio.SPI(clock=board.GP10, MOSI=board.GP11)
#cs = digitalio.DigitalInOut(board.GP13)
#cs.direction = digitalio.Direction.OUTPUT
#leds = bcddigits.BCDDigits(spi, cs, nDigits=8)

#setting up external foot buttons


#setting up external potentiometers
#analog_A = AnalogIn(board.A0)
#analog_B = AnalogIn(board.A1)
#analog_C = AnalogIn(board.A2)


#setting up constants

MIDI_MODE_EXCL=0
MIDI_MODE_YOKED=1
MIDI_MODE_LEARN=2

VOL_MODE_ON=1
VOL_MODE_OFF=0

SONG_MODE_ON=1
SONG_MODE_OFF=1

PAGE_SIZE=16
PAGE_NUMBER=0
PAGE_COUNT=3

NORTH=0
EAST=3
SOUTH=9
WEST=9

gCurrMidiMode=MIDI_MODE_EXCL
gCurrVolMode=SONG_MODE_OFF
gCurrSongMode=SONG_MODE_OFF

currPage = PAGE_NUMBER

#EAST NORTH FOR ACOUSTIC GUITAR
currRpiSide = WEST
currUsbRelToHand = SOUTH
#EDIT THESE DEPENDING ON ORIENTATION

class StateBtn:

    def __init__(self, nId, btn, midi, callback=None, states=None, colors=None, cmdVals=None, ctrlChangeChn=None):
        self.id = nId
        self.btn=btn
        self.midi = midi
        self.state=0
        self.lastPressed=0
        self.callback=callback
        if states==None:
            self.states = [0,0]
        else:
            self.states=states
        if colors==None:
            self.colors = [(0,0,255),(255,0,0)]
        else:
            self.colors=colors
            
        if ctrlChangeChn==None:
            self.ctrlChangeChn=nId
        else:
            self.ctrlChangeChn=ctrlChangeChn
            
        if cmdVals==None:
            self.cmdVals=[1,96]
        else:
            self.cmdVals=cmdVals;
        self.btn.set_led(*self.colors[self.state])
            
 
    def check(self):
        if self.btn.pressed:
            self.wasPressed()
    
    def setCtrlChangeChn(self,ctrlChangeChn):
        self.ctrlChangeChn=ctrlChangeChn
        
    def checkState(self):
        if self.state==len(self.states):
            self.state=0
            
    def wasPressed(self):
        now = time.monotonic()
        if now-self.lastPressed >.2 :
            print("state button", self.id)
            self.upState()
            self.lastPressed=now
            if self.callback!=None:
                self.callback(self.id, self.state)
   
    def upState(self):
        self.state+=1
        self.checkState()
        self.enactState()
        
    def setState(self, state):
        print ("setting self.state, currently ", self.state, " to ", state)
        if state==self.state:
            return
        self.state=state
        self.checkState()
        self.enactState()
        
    def getState(self):
        return self.state
    
    def enactState(self):        
        self.btn.set_led(*self.colors[self.state])
        if self.midi==None: return
        self.midi.send(ControlChange(self.id+40, self.cmdVals[self.state]))


class DrumBtn:
    
    def __init__(self, nId, btn, midi, note, callback=None):
        self.id=nId
        self.note=note
        self.midi = midi
        self.velocity=100
        self.btn=btn
        self.justPressed=False
        self.color=(0, 255, 255)
        self.lastPressed=0
        self.callback = callback
        btn.set_led(*self.color)
        self.btn.led_off()
        
    def noteOn(self):
        global noteBasher
        self.btn.led_on()
        noteBasher.noteOn(self.note)
        self.btn.led_off()
        
    def check(self):
        if self.btn.pressed:
            self.wasPressed()
        
    def noteOff(self):
        self.btn.led_off()
        self.midi.send(NoteOn(self.note, 0))
        
    def justPressed(self):
        return self.justPressed
    
    def wasPressed(self):
        now = time.monotonic()
        if now-self.lastPressed >.2 :
            self.noteOn()
            self.lastPressed=now
            if self.callback!=None:
                self.callback(self.id, now)


class Pot:
    def __init__(self, midi, nId, pin, callback=None):
        self.midi = midi
        self.nId = nId
        self.prevVoltage = 0
        self.pin=pin
        self.analogue = AnalogIn(pin)
        self.callback = callback
        self.currVoltage=0.0
        
    def get_voltage(self, voltage):
        return int((voltage * 127) / 65536)
    
    def check(self):

        currVoltage = self.get_voltage(self.analogue.value)
        if abs(self.prevVoltage-currVoltage)>3:
            self.midi.send(ControlChange(self.nId, currVoltage))
            self.prevVoltage=currVoltage
            if self.callback!=None:
                self.callback(self.nId, currVoltage)
        
class FootSwitch:
    def __init__(self, midi, nId, pin, callback=None):
        self.midi = midi
        self.nId = nId
        self.prevVoltage = 0
        self.pin=pin
        self.state=0
        self.lastPressed=0
        self.btn = digitalio.DigitalInOut(pin)
        self.btn.direction = digitalio.Direction.INPUT
        self.btn.pull = digitalio.Pull.DOWN
        self.callback=callback
    
    def check(self):
        if self.btn.value:
            print(self.nId)
      
    def wasPressed(self):
            now = time.monotonic
            if now-lastPressed >.2 :
                changeState()
                self.lastPressed=now
                enactState()
                self.callback(nId, self.state)
            
    def changeState(self):
        if self.state==0: self.state=1
        else: self.state=0
        
    def enactState(self):
        self.midi.send(nId, 1+self.state*96)

class MatrixKeypad:
    def __init__(self, midi, nId, rows, cols, callback=None):
        self.rows = rows
        self.cols = cols
        self.nId = nId
        self.midi = midi
        self.callback = callback
        self.row_pins = [Pin(pin_name, mode=Pin.OUT) for pin_name in rows]
        self.col_pins = [Pin(pin_name, mode=Pin.IN, pull=Pin.PULL_DOWN) for pin_name in cols]
        for row in range(0,4):
            for col in range(0,4):
                row_pins[row].low()
                
class AnKeyPad:
    def __init__(self, midi, nId, pin, callback=None):
        self.midi = midi
        self.nId = nId
        self.prevVoltage = 0
        self.pin=pin
        self.analogue = AnalogIn(pin)
        self.callback = callback
        self.currVoltage=0.0
        self.notches = [29,33,40,49,54,57,59,62,69,74,78,83,97,106,115,126]
        self.notchMap=[0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15]
        self.velocity=100
        self.lastPressed = time.monotonic()
        
    def get_voltage(self, voltage):
        return int((voltage * 127) / 65536)
    
    def set_notches(self,notches, notchmap):
        self.notches = notches
        self.notchMap = notchmap
    
    def check(self):
        
        now = time.monotonic()
        currVoltage = self.get_voltage(self.analogue.value)
        if currVoltage<25:
            self.prevVoltage=currVoltage
            return    
        
        if  abs(self.prevVoltage-currVoltage)>3 and  now-self.lastPressed >.1:
            
            nearestIdx = min(range(len(self.notches)), key=lambda i: abs(self.notches[i]-currVoltage))            
            self.prevVoltage=currVoltage
            
            self.lastPressed = now
            if self.callback!=None:
                self.callback(self.nId, self.notchMap[nearestIdx])
                
class MidiReader:
    
    global monitor
    
    def __init__(self, midi):      
        self.midi = midi
          
    def displayMidiMessage(self,msg_in):        
        if msg_in is None:
            return
        if isinstance(msg_in, ProgramChange):
            monitor.update(str(msg_in.patch))
            self.showMidiNum(msg_in.patch)
      


class NoteBasher:
    
    global monitor
    def __init__(self, midi, defVelocity=100, defDuration=.1):
        self.noteQueue=[]
        self.midi = midi
        self.duration=defDuration
        self.velocity=defVelocity
        self.last=0
        
    def noteOn(self,note):
        #clear previous - use this if not using tidyUp() for the noteoffs
        
        noteOffs = [tup for tup in self.noteQueue]
        for index, tup in enumerate(noteOffs):
            self.midi.send(NoteOn(tup[0], 0))
            print ("noteOff on", tup[0]);
        self.noteQueue=[]
        ##################################
        noteTuple=tuple([note,time.monotonic()])
        self.noteQueue.append(noteTuple)
        #monitor.statusUpdate(str(noteTuple[0]))
        self.midi.send(NoteOn(note, self.velocity))
        
    def queueLength(self):
        return len(self.noteQueue)
        
    def tidyUp(self):
        if len(self.noteQueue)==0: return
        noteOffs = [tup for tup in self.noteQueue if time.monotonic()-tup[1]> .05]
        for index, tup in enumerate(noteOffs):
            self.midi.send(NoteOn(tup[0], 0))
            print ("noteOff on", tup[0]);
        self.noteQueue = [x for x in self.noteQueue if x not in noteOffs]


class Setting:
    def __init__(self, val, min, max, incAmt):
        self.val = val
        self.min = min
        self.max = max
        self.incAmt = incAmt
        
    def inc(self):
        self.val = min(self.val+self.incAmt,self.max)
        
    def dec(self):
        self.val = max(self.val-self.incAmt,self.min)
        

class Settings:
    global monitor
    def __init__(self):
        self.PAGE=0
        self.ITEM=1
        self.board=0
        self.snapshot=0
        self.masterkey = dict(channel=0, nav=1,cc=2,tempo=3)
        self.midiChn = dict(channel = Setting(0,0,15,1))
        self.nav = dict(board = Setting(0,0,15,1), snapshot = Setting(0,0,15,1))
        self.cc =  dict(ccnum = Setting(0,0,127,1), ccval = Setting(0,0,127,1))
        self.tempo = dict(bpm = Setting(120,80,160,5), bpb = Setting(1,1,8,1))
        self.masterlist = [self.midiChn,self.nav,self.cc, self.tempo]
        self.cursor = [0,0]
        
    def nextPage(self):
        if self.cursor[self.PAGE]==len(self.masterlist):
            self.cursor[self.PAGE]=0
        else: self.cursor[self.PAGE]+=1
        
    def nextItemInPage(self):
        if self.cursor[self.ITEM]==len(self.masterlist[self.cursor[self.PAGE]])-1:
            self.cursor[self.ITEM]=0
        else: self.cursor[self.ITEM]+=1
        
    def nextItem(self):
        if self.cursor[self.ITEM]==len(self.masterlist[self.cursor[self.PAGE]])-1:  #if at end of page
            if self.cursor[self.PAGE]==len(self.masterlist)-1: #if at end of sequence of pages too
                self.cursor[self.PAGE]=0
                self.cursor[self.ITEM]=0
            else:
                self.cursor[self.PAGE]+=1
                self.cursor[self.ITEM]=0
        else:
            self.cursor[self.ITEM]+=1
        monitor.refresh()
            
    def prevItem(self):
        if self.cursor[self.ITEM]==0:  #if at beginning of page
            if self.cursor[self.PAGE]==0: #if at beginning of sequence of pages too
                self.cursor[self.PAGE]=len(self.masterlist)-1
                self.cursor[self.ITEM]=len(self.masterlist[self.cursor[self.PAGE]])-1
            else:
                self.cursor[self.PAGE]-=1
                self.cursor[self.ITEM]=len(self.masterlist[self.cursor[self.PAGE]])-1
        else:
            self.cursor[self.ITEM]-=1
        monitor.refresh()
    
    def getPages(self):
        return self.masterkey.keys
    
    def getPageItems(self,pgNum):
        return self.masterlist[pgNum].keys
    
    def getPageItemValue(self,pgNum,itemName):
        return self.masterlist[pgNum][itemName]
    
    def setPageItemValue(self,pgNum,itemName,itemValue):
        self.masterlist[pgNum][itemName] = itemValue
        
    def findPage(self,itemName):
        for i in range(len(self.masterlist)):
            if itemName in self.masterlist[i]:
                return i
        return -1
    
    def getItemValue(self,itemName):
        pgNum = findPage(itemName)
        if pgNum>-1:
            return getPageItemValue(pgNum,itemName)
        return "not found"
    
    def setItemValue(self,itemName):
        pgNum = findPage(itemName)
        if pgNum>-1:
            self.masterlist[findPage(itemName)][itemName] = itemValue
            
    def incrementCurrItem(self):
        self.changeVal(1)
        
    def decrementCurrItem(self):
        self.changeVal(-1)
        
    def changeVal(self, amt):
        key = self.getKeyFromPos()
        if amt>0:pageDict[key].inc()
        else:pageDict[key].dec()
        monitor.refresh()
        
    def getKeyFromPos(self):
        pgNum=self.cursor[self.PAGE]
        itNum = self.cursor[self.ITEM]
        pageDict = self.masterlist[pgNum]
        keys = list(pageDict.keys())
        key = keys[itNum]
        return key
    
    def enactState(self):
        pgNum=self.cursor[self.PAGE]
        if pgNum==1:#nav
            print("Program Change", self.getKeyFromPos()); 
        if pgNum==2:
            print("Send a specified CC message", self.getKeyFromPos())
        if pgNum==3:
            print("Send a CC message to change tempo", self.getKeyFromPos())
        
        
        

class Monitor:
    
    def __init__(self, dizplay, settings):
        self.settings = settings
        self.display = dizplay
        self.splash = displayio.Group()
        self.display.show(self.splash)
        self.buffer = ""
        self.status = "Start"
        self.keyAreas = []
        self.valAreas = []

        self.addKvP("", "", 0, 0xFFFFFF)
        self.addKvP("", "", 1, 0x999999)
        self.addKvP("", "", 2, 0x999999)
        self.addKvP("", "", 3, 0x999999)
        self.addKvP("NEXT", "", 4, 0x999999)
        self.addKvP(self.status, "5", 5, 0xFF0000)
        print(self.keyAreas)
        print(self.valAreas)
        
        
    def refresh(self):
        pg = self.settings.cursor[0]
        item = self.settings.cursor[1]
        ct=0
        for key, value in self.settings.masterlist[pg].items():
            self.showKvP(key,value.val,ct,item==ct)
            ct+=1
            
     
    def showKvP(self, key, val, pos, lit):
        self.keyAreas[pos].text = str(key)
        self.valAreas[pos].text = str(val)
        if lit:
            self.keyAreas[pos].color=0xFFFFFF
            self.valAreas[pos].color=0xFFFFFF
        else:
            self.keyAreas[pos].color=0x999999
            self.valAreas[pos].color=0x999999
        
    
    def statusUpdate(self, txt):
        self.status= txt
        self.valAreas[5].text = "\n".join(wrap_text_to_lines(self.status, 20))
        self.settings.nextItem()
        self.refresh()
        
    def statusAppend(self, txt):
        self.status= self.status + txt
        self.valAreas[5].text = "\n".join(wrap_text_to_lines(self.status, 20))
        
    def addKvP(self, key, defValue, pos,col):
        key_group = displayio.Group(scale=2, x=0, y=10+(pos*40))
        key_area = label.Label(terminalio.FONT, text=key, color=col)
        self.keyAreas.append(key_area)
        key_group.append(key_area)  # Subgroup for text scaling
        self.splash.append(key_group)
        val_group = displayio.Group(scale=2, x=180, y=10+(pos*40))
        val_area = label.Label(terminalio.FONT, text=defValue, color=col)
        self.valAreas.append(val_area)
        val_group.append(val_area)  # Subgroup for text scaling
        self.splash.append(val_group)
        
        


#SET UP MIDI CHANNELS TO USE

midi1 = adafruit_midi.MIDI(
    midi_in=usb_midi.ports[0],
    midi_out=usb_midi.ports[1],
    in_channel=0,
    out_channel=9,
)
midi2 = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=10)


note = 60
velocity = 127

def drumBtnPressed(ctrlId,when):
    global drumNotesPlayed
    #notewhen = {"ctrlId":ctrlId, "when":when}
    #drumNotesPlayed.append(notewhen)
    print ("Note played from button ", ctrlId)
    
def doNotesOff():
    global drumNotesPlayed
    global Controlz
    currTime = time.monotonic()
    #print(len(drumNotesPlayed))
    for i in range(len(drumNotesPlayed) - 1, -1, -1):
        thisEvtSrc = drumNotesPlayed[i]
        if currTime-thisEvtSrc["when"] > 0.1:
            Controlz[thisEvtSrc["ctrlId"]].noteOff()
            print ("Note off", thisEvtSrc["ctrlId"])
            del drumNotesPlayed[i]
            
 
def stateBtnPressed(id, state): #turning off all the other fx but not the one just turned on
    global fxkeys
    if gCurrMidiMode==MIDI_MODE_EXCL or gCurrMidiMode==MIDI_MODE_YOKED:
        if id in fxkeys:
            for fxkey in fxkeys:
                if fxkey!=id and state==1:
                    Controlz[fxkey].setState(0)
    if gCurrMidiMode==MIDI_MODE_YOKED and state==1:
        if id in loopkeys:
            for fxkey in fxkeys:
                Controlz[fxkey].setState(0)
            Controlz[loopFxTethers[id]].setState(1)
            
    
def footPedalPressed(id, state):
    global debugging
    if debugging: print(id,state)
    
def potMoved(id,state):
    global debugging
    if debugging: print(id,state)
    
def barsPressed(id, state):
    global debugging
    if debugging: print(id,state)
    
def midiModePressed(id, state):
    global gCurrMidiMode
    print("Midi Mode Pressed")
    gCurrMidiMode=state
    print(id,state)
    
#reset - the toggling of volume and loop handled by midilearn
#when in non-midilearn state, just switches off all loopsand fx
#sets midi back to exclusive mode
def resetPressed(id, state):
    global gCurrMidiMode
    if gCurrMidiMode==MIDI_MODE_LEARN: return
    #turning all loops off (regardless of ending or starting song)
    for loopkey in loopkeys:
        Controlz[loopkey].setState(0)
    #turning all fx off (regardless of ending or starting song)
    for fxkey in fxkeys:
        Controlz[fxkey].setState(0)
    #going to midi mode exclusive (regardless of ending or starting song)
    Controlz[exkeys[0]].setState(MIDI_MODE_EXCL);
    # if restarting turning off the fade state
    if state==1:
        Controlz[exkeys[1]].setState(state);

def soundFadePressed(id, state):
    global debugging
    if debugging: print("Sound Fade Pressed")
    
def drumPadPressed(id, value):
    global debugging
    global noteBasher
    if debugging: print(id, value)
    noteBasher.noteOn(value+36)
    
def pagerPressed(id, value):
    global debugging
    global settings
    if debugging: print(id, value)
    if value==2:
        settings.prevItem()
    if value==4:
        settings.nextItem()
    if value==1:
        settings.decrementCurrItem()
    if value==3:
        settings.incrementCurrItem()
    if value==0:
        settings.enactState()
        
    
    
    
        
if currRpiSide==NORTH:

    if currUsbRelToHand==NORTH:
        drumkeys = [12,13,14,15]
        loopkeys  = [8,9,10,11]
        fxkeys = [4,5,6,7]
        exkeys = [0,1,2,3]
        gmDrums = [36,40,44,48]
        
    if currUsbRelToHand==WEST:
        drumkeys = [0,4,8,12]
        loopkeys  = [2,6,10,14]
        fxkeys= [1,5,9,13]
        exkeys = [3,7,11,15]
        gmDrums = [36,40,44,48]

    if currUsbRelToHand==SOUTH:
        drumkeys = [3,2,1,0]
        loopkeys = [7,6,5,4]
        fxkeys = [11,10,9,8]
        exkeys = [3,7,11,15]
        gmDrums = [48,44,30,36]

    if currUsbRelToHand==EAST:
        drumkeys = [15,11,7,3]
        loopkeys  = [14,10,6,2]
        fxkeys= [13,9,5,1]
        exkeys = [12,8,4,0]
        gmDrums = [48,44,30,36]

if currRpiSide==WEST:

    if currUsbRelToHand==SOUTH:
        drumkeys = [3,2,1,0]
        loopkeys  = [15,7,6,5,4]
        fxkeys = [11,10,9,8]
        exkeys = [14,13,12]
        gmDrums = [36,40,44,48]
        loopFxTethers = {7:11,6:10,5:9,4:8}
        print (drumkeys)



#footPedalPins = [board.GP20,board.GP21]
#analoguePins = [board.A0,board.A1]

gmDrums = [36,37,38,39]

#utility singleton classes
noteBasher = NoteBasher(midi1, 100, .1)
midiReader = MidiReader(midi1)


Controlz = {}
ct=0
for keynum in drumkeys:
    Controlz[keynum]=DrumBtn(keynum, keys[keynum], midi1, gmDrums[ct], drumBtnPressed)
    ct=ct+1
    
for keynum in fxkeys:
    Controlz[keynum]=StateBtn(keynum, keys[keynum], midi1,stateBtnPressed,[0,0],[(128,128,128),(255,0,0)])
    ct=ct+1
    
for keynum in loopkeys:
    Controlz[keynum]=StateBtn(keynum, keys[keynum], midi1, stateBtnPressed,[0,0],[(0,0,255),(255,0,0)])
    ct=ct+1
    

    
ctrlCt=16  #
# for footPedalPin in footPedalPins:
#     Controlz[ctrlCt] = FootSwitch(midi1, ctrlCt, footPedalPin, footPedalPressed)
#     ctrlCt+=1
# 
# for aPin in analoguePins:
#     Controlz[ctrlCt] = Pot(midi1, ctrlCt, aPin, potMoved)
#     ctrlCt+=1
    
drumPad = AnKeyPad(midi1, ctrlCt, board.A2, drumPadPressed)
pagerPad = AnKeyPad(midi1, ctrlCt, board.A1, pagerPressed)

pagerPad.set_notches([36,64,87,110,126],[0,1,2,4,3])

Controlz[ctrlCt] = drumPad
Controlz[ctrlCt+1] = pagerPad


                  
settings = Settings()


displayio.release_displays()
tft_cs = board.GP13
tft_dc = board.GP12
spi_mosi = board.GP11
spi_clk = board.GP10
spi = busio.SPI(spi_clk, spi_mosi)
display_bus = displayio.FourWire(spi, command=tft_dc, chip_select=tft_cs)
display = ST7789(display_bus, width=240, height=240, rowstart=80, rotation=90)
monitor = Monitor(display, settings)


# bars button
rgbs = [(255,0,0),(0,255,0),(0,0,255),(255,255,0),(255,0,255),(255,255,255)]
cmdVals = [4,12,28,60,96,127]
states=[0,1,2,3,4,5]
currKey=exkeys[0]
#Controlz[currKey] = StateBtn(currKey, keys[currKey], midi1, barsPressed, states, rgbs, cmdVals)

#midi mode button
#def __init__(self, nId, btn, midi, callback=None, states=None, colors=None, cmdVals=None, ctrlChangeChn=None):
#currKey=exkeys[1]

#three midi modes - exclusive (only one fx at a time), yoked (as before, but turning on loop turns on corresponding fx)
# and learn - when just getting the pedalboard to follow the commands
MidiModeColors = [(255,255,0),(255,0,0),(0,0,255)]
Controlz[exkeys[0]] = StateBtn(currKey, keys[exkeys[0]], None, midiModePressed, [0,1,2], MidiModeColors)

#volume off button
currKey=exkeys[1]
Controlz[exkeys[1]] = StateBtn(currKey, keys[exkeys[1]], midi1, soundFadePressed)

#reset button (also does volume on/off)
currKey=exkeys[2]
Controlz[exkeys[2]] = StateBtn(currKey, keys[exkeys[2]], midi1, resetPressed)



def get_voltg(raw):
    return (raw * 3.3) / 65536

while True:
    
    keybow.update()
    
    for i in range(0,len(Controlz)):
            Controlz[i].check()
     
    
    noteBasher.tidyUp()
    midiReader.displayMidiMessage(midi1.receive())
    

    

     
        
    




        






