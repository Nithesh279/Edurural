import asyncio
import edge_tts
import os

async def test():
    c1 = edge_tts.Communicate('Hello', 'en-US-AriaNeural')
    c2 = edge_tts.Communicate('World', 'en-US-AriaNeural')
    
    with open('t1.mp3', 'wb') as f:
        async for m in c1.stream():
            if m['type'] == 'audio': f.write(m['data'])
            
    with open('t2.mp3', 'wb') as f:
        async for m in c2.stream():
            if m['type'] == 'audio': f.write(m['data'])
            
    with open('combined.mp3', 'wb') as f:
        f.write(open('t1.mp3', 'rb').read())
        f.write(open('t2.mp3', 'rb').read())
    
    print("Combined sizes:", os.path.getsize('combined.mp3'))

asyncio.run(test())
