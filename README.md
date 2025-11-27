# Step Tools
<div align="center">
  <img src=".meta/preview_1.png" width="800"/> <br>
</div>

Blender3D addon that automates the process of creating object blink animations. <br>
Created for use in technical animation.

## Features
- Blinking transparency
- Custom blink color selection
- Adjust blink duration and count
- Quick application of fade effects with customizable settings
- Automatic insertion of markers for easy step separation
- Saving markers to a file to create pauses in the Video Sequencer

<div align="center">
  <img src=".meta/preview_anim_1.gif" width="800"/> <br>
</div>

## How it works
The addon creates several "Custom Properties" and a shader node group with attributes for the selected objects. <br>
The group is created before the "Material Output" node and does not affect existing shader settings.
<div align="center">
  <img src=".meta/preview_2.png" height="120"/>  <img src=".meta/preview_3.png" height="120"/>
</div>

<br>

Keyframes are set on the objects "Custom Properties". <br>
This improves performance when working with a large number of materials.
<div align="center">
  <img src=".meta/preview_anim_2.gif" width="800"/> <br>
</div>

## Installation
Download the .zip file and follow the [official instructions](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html) for installing addons (Install from Disk).

## Download
Link for download [last release](https://github.com/vgmove/step-tools/releases/download/release_v1.0.0/step_tools.zip). 
