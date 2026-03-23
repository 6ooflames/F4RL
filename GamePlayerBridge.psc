Scriptname GamePlayerBridge extends Quest

Actor Property PlayerRef Auto

Event OnInit()
    Debug.OpenUserLog("GamePlayerSession")
    StartTimer(2.0, 1) ; Tick every 2 seconds
EndEvent

Event OnTimer(int aiTimerID)
    if aiTimerID == 1
        ; Gather Vitals
        float currentHP = PlayerRef.GetValue(Game.GetForm(0x000002D4) as ActorValue) ; Health
        float maxHP = PlayerRef.GetBaseValue(Game.GetForm(0x000002D4) as ActorValue)
        
        float currentAP = PlayerRef.GetValue(Game.GetForm(0x000002D5) as ActorValue) ; ActionPoints
        float maxAP = PlayerRef.GetBaseValue(Game.GetForm(0x000002D5) as ActorValue)
        
        int level = PlayerRef.GetLevel()
        
        ; Gather Location
        Location currentLocation = PlayerRef.GetCurrentLocation()
        String locName = "Commonwealth"
        if currentLocation
            locName = currentLocation.GetName()
        endif

        ; Format as a single JSON line to the log
        String jsonDump = "{\"location\":\"" + locName + "\", \"hp\":\"" + (currentHP as int) + "/" + (maxHP as int) + "\", \"ap\":\"" + (currentAP as int) + "/" + (maxAP as int) + "\", \"level\":\"" + level + "\"}"
        
        Debug.TraceUser("GamePlayerSession", jsonDump)
        
        ; Loop
        StartTimer(2.0, 1)
    endif
EndEvent
