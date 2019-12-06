import os
import pathlib
import subprocess


def convert_to_mkv_ffmpeg(video_file):
    file = pathlib.Path(video_file)
    # ffmpeg -i <INPUT> -vcodec copy -ss 00:00:00 -force_key_frames 00:00:00 -map 0:0 -sn -map_metadata 0 <OUTPUT>
    args = f'ffmpeg -i {str(file)} -vcodec copy -ss 00:00:00 -force_key_frames 00:00:00 -map 0:0 -sn -map_metadata 0 {str(file.with_suffix(".mkv"))} -y'
    p = subprocess.run(args.split(' '))
    if p.returncode == 0:
        return True
    return False


def convert_to_mkv_mkvtoolnix(video_file):
    file = pathlib.Path(video_file)
    # /usr/bin/mkvmerge --output test.mkv --no-audio --language 0:und '(' test.ts ')'
    args = f"mkvmerge --output {str(file.with_suffix('.mkv'))} --no-audio --language 0:und " + f"{str(file)}"
    p = subprocess.run(args.split(' '))
    if p.returncode == 0:
        return True
    return False


if __name__ == '__main__':
    INPUT = r'/home/ashibaev/Documents/ЗИП_АХТУНГ/Ivanovo/ОТР/video'
    OUTPUT = r'/home/ashibaev/Documents/ЗИП_АХТУНГ/Ivanovo/ОТР/video'

    for root, dirs, files in os.walk(INPUT):
        for file in files:
            p = os.path.join(root, file)
            if p.endswith(".ts"):
                convert_to_mkv_mkvtoolnix(p)