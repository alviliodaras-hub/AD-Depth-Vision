import av
import os
import shutil

def convert_for_web(input_path):
    if not os.path.exists(input_path) or not input_path.endswith('.mp4'):
        return
        
    temp_path = input_path.replace('.mp4', '_tmp.mp4')
    print(f"[Web Encode] Optimizing {input_path} for Safari...")
    
    try:
        input_container = av.open(input_path)
        
        # If no video stream, exit
        if not input_container.streams.video:
            input_container.close()
            return
            
        in_video = input_container.streams.video[0]
        
        # Get framerate safely — fallback chain: average_rate -> base_rate -> guessed_rate -> 30
        fps = in_video.average_rate
        if fps is None or fps == 0:
            fps = in_video.base_rate
        if fps is None or fps == 0:
            fps = in_video.guessed_rate
        if fps is None or fps == 0:
            fps = 30
        
        # Ensure dimensions are even (H.264 requirement)
        width = in_video.width
        height = in_video.height
        if width % 2 != 0:
            width -= 1
        if height % 2 != 0:
            height -= 1
        
        output_container = av.open(temp_path, 'w', format='mp4')
        
        # Safari strict requirements: libx264, yuv420p, faststart
        out_video = output_container.add_stream('libx264', rate=fps)
        out_video.width = width
        out_video.height = height
        out_video.pix_fmt = 'yuv420p'
        out_video.options = {'preset': 'ultrafast', 'movflags': 'faststart', 'crf': '23'}
        
        frame_count = 0
        for frame in input_container.decode(in_video):
            # Ensure PTS is set (some OpenCV outputs have None PTS)
            if frame.pts is None:
                frame.pts = frame_count
            
            # Resize if dimensions were adjusted for even alignment
            if frame.width != width or frame.height != height:
                frame = frame.reformat(width=width, height=height)
            
            for packet in out_video.encode(frame):
                output_container.mux(packet)
            frame_count += 1
                
        # Flush
        for packet in out_video.encode():
            output_container.mux(packet)
            
        input_container.close()
        output_container.close()
        
        # Replace original
        shutil.move(temp_path, input_path)
        print(f"[Web Encode] Success. Encoded {frame_count} frames.")
    except Exception as e:
        print(f"[Web Encode] Error: {e}")
        import traceback
        traceback.print_exc()
        if os.path.exists(temp_path):
            os.remove(temp_path)
