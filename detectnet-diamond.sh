#!/bin/bash
set -x
while :
do
# headless
./detectnet-diamond.py --headless=true  --camera=/dev/video0 --width=640 --height=480 --model=models/diamond/ssd-mobilenet.onnx --labels=models/diamond/labels.txt --input-blob=input_0 --output-cvg=scores --output-bbox=boxes 
done
