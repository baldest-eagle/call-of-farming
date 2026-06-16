schtasks /Delete /TN "FarmCycle" /F
schtasks /Create /TN "FarmCycle" /TR "C:\Users\kyleh\AppData\Local\Programs\Python\Python312\pythonw.exe C:\Users\kyleh\.gemini\BotProject\farm_cycle.py" /SC DAILY /ST 17:21 /RI 180 /DU 24:00 /RL HIGHEST /F
