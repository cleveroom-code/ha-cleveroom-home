class BufferType:
    GWBUFFER = 0
    VERSIONBUFFER = 1
    VOLBUFFER = 2
    DEVICEBUFFER = 3
    ALARMBUFFER = 4
    SECURITYBUFFER = 5
    FMBUFFER = 6
    SENSORBUFFER = 7
    TIMEBUFFER = 8
    CACHEBUFFER = 9
    CLOCKBUFFER = 10
    GWPASSWORDBUFFER = 11
    ENERGYBUFFER = 12
    ENERGYHISTORYBUFFER = 13
    SCENEBUFFER = 14
    RGBBUFFER = 15
    WATERMETERBUFFER = 16
    WATERMETERHISTORYBUFFER = 17
    SPEAKERBUFFER = 18
    SENSOREXBUFFER = 19
    COUNTERBUFFER = 20
    COMBINEBUFFER = 21
    CURTAINBUFFER = 22
    MODULEBUFFER = 23
    PLCWRITEFEEDBACK = 24
    EVENTBUFFER = 25


class DeviceType:
    """Device type constant definitions"""
    # Switch
    TOGGLE = 0
    # Ordinary light
    TOGGLE_LIGHT = 1
    # Adjustable light/device
    ADJUST_LIGHT = 2
    # Color light
    RGB_LIGHT = 3
    # Dual-color light
    WARM_LIGHT = 4
    # Dual-color light with W
    RGBW_LIGHT = 5
    # Curtain
    CURTAIN = 6
    # Speaker, background music
    MUSIC_PLAYER = 7
    # Air conditioner
    AIR_CONDITION = 8
    # Fresh air
    FRESH_AIR = 9
    # Floor heating
    FLOOR_HEATING = 10
    # Scene
    SCENE = 11
    # Sensor
    SENSOR = 12
    # Dry contact
    DRY = 13
    # Security
    SECURITY = 14
    # Timer
    CLOCK = 15
    # System time
    TIMER = 16
    # Alarm data
    ALARM = 17
    # Ammeter
    AMMETER = 18
    # Water meter
    WATERMETER = 19
    # Gas meter
    GASMETER = 20
    #Event
    EVENT = 21
