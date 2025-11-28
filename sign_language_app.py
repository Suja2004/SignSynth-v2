import os
import sys
import json
import nltk
import time
import win32com.client
from direct.task import Task
import sounddevice as sd
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DGG
from direct.gui.DirectFrame import DirectFrame
from direct.gui.DirectButton import DirectButton
from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectLabel import DirectLabel
from direct.gui.DirectOptionMenu import DirectOptionMenu
from direct.gui.DirectSlider import DirectSlider
from direct.interval.IntervalGlobal import Sequence, LerpFunc, Wait, Func
from direct.interval.LerpInterval import LerpPosInterval, LerpHprInterval
from panda3d.core import (LVecBase3f, DirectionalLight, AmbientLight, TextNode, WindowProperties, Filename,
                          TransparencyAttrib)

try:
    nltk.data.find('tokenizers/punkt_tab')
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('corpora/wordnet')
    nltk.data.find('taggers/averaged_perceptron_tagger')
    nltk.data.find('corpora/omw-1.4')
except LookupError:
    nltk.download('punkt_tab', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('omw-1.4', quiet=True)

from speech_gloss import SpeechGloss


class SignLanguageApp(ShowBase):
    """
    Integrates 3D model, sign pose animation, UI, speech recognition, and media control for sign language display.
    """

    def __init__(self, version):
        ShowBase.__init__(self)
        
        self.version = version

        self.loadModels()
        self.setupLights()
        self.setupSkybox()

        try:
            self.current_pose = "default"
            self.gesture_data = self.loadAllPoseData()
            self.loadSignPoses(self.current_pose)
            self.expanded_sequence = []
            self.pose_index = 0
            self.is_animating = False
        except Exception as e:
            print(f"Could not load pose data: {e}")

        self.media_control_active = False
        self.sign_delay = 1.5
        self.play_interval = 5
        self.pause_interval = 5
        self.last_media_action_time = 0
        self.media_state = "paused"
        self.speech_recognition_active = False
        self.speech_processor = None
        self.is_animating = False
        self.signing_complete = True

        self.selected_device_index = None
        self.audio_source_mode = "MIC"
        self.available_devices = []

        self.setup_ui()
        self.start_speech_recognition()
        self.setup_media_control()

    def open_app_window(self):
        """
        Manually opens the main Panda3D window and runs all
        window-dependent setup code.
        """
        if self.openDefaultWindow():
            print("Successfully opened Panda3D window.")

            props = WindowProperties()
            props.setTitle("SignSynth")

            icon_path = self.get_resource_path("SignSynth.ico")

            if os.path.exists(icon_path):
                panda_icon_path = Filename.fromOsSpecific(icon_path)
                props.setIconFilename(panda_icon_path)
            else:
                print(f"Warning: Icon file not found at {icon_path}")

            self.win.requestProperties(props)
            self.disableMouse()
            self.camera.setPos(0, -15, 3.25)
            self.camera.lookAt(0, 0, 0)
        else:
            print("Error: Failed to open Panda3D window.")

    def add_tooltip(self, button, text):
        tooltip = OnscreenText(
            text=text,
            style=1,
            fg=(1, 1, 1, 1),
            bg=(0, 0, 0, 0),
            scale=0.5,
            pos=(2, 0),
            mayChange=True,
            wordwrap=6,
            align=TextNode.ACenter
        )
        tooltip.hide()
        button.bind(DGG.ENTER, lambda event: tooltip.show())
        button.bind(DGG.EXIT, lambda event: tooltip.hide())
        tooltip.reparentTo(button)

    def toggle_tab(self):
        if self.settings_frame.isHidden():
            self.settings_frame.show()
        else:
            self.settings_frame.hide()

    def setup_ui(self):
        """
        Create a consolidated, on-screen user interface panel.
        """
        FRAME_COLOR = (0.1, 0.1, 0.1, 0)
        TEXT_COLOR = (1, 1, 1, 1)
        ICON_SIZE = 0.085
        BTN_X_POS = 0.55
        
        self.ui_frame = DirectFrame(
            frameColor=FRAME_COLOR,
            frameSize=(-1.3, 1.3, -0.25, 0.25),
            pos=(0.4, 0, -0.7)
        )

        self.top_bar_frame = DirectFrame(
            frameColor=FRAME_COLOR,
            frameSize=(-1.3, 1.3, -0.25, 0.25),
            pos=(0.1, 0, 0.5)
        )

        self.recognized_text_label = OnscreenText(
            parent=self.ui_frame, text="Current Sign:", pos=(-1.2, 0.1), scale=0.06,
            fg=TEXT_COLOR, align=TextNode.ALeft, mayChange=False
        )

        self.recognized_text_node = OnscreenText(
            parent=self.ui_frame, text="...", pos=(-0.65, 0.1), scale=0.06,
            fg=TEXT_COLOR, align=TextNode.ALeft, mayChange=True
        )

        self.gloss_text_label = OnscreenText(
            parent=self.ui_frame, text="Signing (Gloss):", pos=(-1.2, -0.1), scale=0.06,
            fg=TEXT_COLOR, align=TextNode.ALeft, mayChange=False
        )

        self.gloss_text_node = OnscreenText(
            parent=self.ui_frame, text="Ready to listen.", pos=(-0.65, -0.1), scale=0.06,
            fg=TEXT_COLOR, align=TextNode.ALeft, wordwrap=20, mayChange=True
        )

        def create_icon_button(img_name, z_pos, cmd, tooltip_text):
            btn = DirectButton(
                parent=self.top_bar_frame,
                image=f"assets/icons/{img_name}",
                scale=ICON_SIZE,
                command=cmd,
                pos=(BTN_X_POS, 0, z_pos),
                relief=None
            )
            btn.setTransparency(TransparencyAttrib.MAlpha)
            self.add_tooltip(btn, tooltip_text)
            return btn

        self.reset_button = create_icon_button("reset.png", 0.3, self.reset_app, "Reset")
        self.speech_toggle_button = create_icon_button("speech-recognition-on.png", 0.1, self.toggle_speech_recognition, "Speech Recognition")
        self.media_toggle_button = create_icon_button("media-control-off.png", -0.1, self.toggle_media_control, "Media Control")
        self.settings_tab_button = create_icon_button("settings.png", -1, self.toggle_tab, "Settings")
        
        self.setup_settings_tab()

    def setup_settings_tab(self):
        """
        Sets up the Audio Settings UI panel with improved alignment and backend hooks.
        """
        self.settings_frame = DirectFrame(
            frameColor=(0.15, 0.15, 0.15, 0.95),
            frameSize=(-0.7, 0.7, -0.6, 0.6),
            pos=(0, 0, 0),
            parent=self.aspect2d
        )
        self.settings_frame.hide()

        DirectLabel(
            parent=self.settings_frame,
            text="General Settings",
            scale=0.07,
            pos=(0, 0, 0.45),
            text_fg=(1, 1, 1, 1),
            frameColor=(0, 0, 0, 0)
        )

        self.close_tab_btn = DirectButton(
            parent=self.settings_frame,
            pos=(0.6, 0, 0.5),
            command=self.toggle_tab,
            image="assets/icons/close.png",
            scale=0.05,
            relief=None
        )

        DirectLabel(
            parent=self.settings_frame,
            text="Sign Delay:",
            scale=0.05,
            pos=(-0.5, 0, 0.25),
            text_align=TextNode.ALeft,
            text_fg=(0.8, 0.8, 0.8, 1), frameColor=(0, 0, 0, 0)
        )

        self.delay_value_label = DirectLabel(
            parent=self.settings_frame,
            text=f"{self.sign_delay:.1f}s", scale=0.05, pos=(0.5, 0, 0.25),
            text_fg=(1, 1, 1, 1), frameColor=(0, 0, 0, 0)
        )

        def update_delay():
            val = self.delay_slider['value']
            self.sign_delay = round(val, 1)
            self.delay_value_label['text'] = f"{self.sign_delay:.1f}s"

        self.delay_slider = DirectSlider(
            parent=self.settings_frame,
            range=(0.5, 2.0),
            value=self.sign_delay,
            pageSize=0.1,
            scale=0.4,
            pos=(0, 0, 0.2),
            command=update_delay,
            thumb_frameColor=(0.8, 0.8, 0.8, 1),
            frameColor=(0.3, 0.3, 0.3, 1)
        )

        DirectLabel(
            parent=self.settings_frame,
            text="Select Device:",
            scale=0.05,
            pos=(-0.5, 0, 0.05),
            text_align=TextNode.ALeft,
            text_fg=(0.8, 0.8, 0.8, 1),
            frameColor=(0, 0, 0, 0)
        )

        self.device_menu = DirectOptionMenu(
            parent=self.settings_frame,
            scale=0.05,
            pos=(-0.5, 0, -0.05),
            items=["Loading..."],
            command=self.on_device_selected,
            text_align=TextNode.ALeft,
            popupMarker_scale=0.5,
            frameColor=(0, 0, 0, 0),
            text_fg=(1, 1, 1, 1),
            popupMenu_frameColor=(0, 0, 0, 0),
            popupMenu_text_fg=(1, 1, 1, 0)
        )

        self.populate_audio_devices()

        self.apply_btn = DirectButton(
            parent=self.settings_frame,
            image="assets/icons/apply.png",
            pos=(0, 0, -0.25),
            command=self.restart_speech_service,
            scale=0.1,
            relief=None
        )
        
        for btn in [self.close_tab_btn, self.apply_btn]:
            btn.setTransparency(TransparencyAttrib.MAlpha)
            
        DirectLabel(
            parent=self.settings_frame,
            text=self.version,
            scale=0.07,
            pos=(0, 0, -0.5),
            text_fg=(1, 1, 1, 1),
            frameColor=(0, 0, 0, 0)
        )

    def populate_audio_devices(self):
        """
        Scans system for devices. On Windows, filters for MME drivers to ensure compatibility with VOSK's 16kHz requirement.
        """
        try:
            devices = sd.query_devices()
            host_apis = sd.query_hostapis()

            valid_api_index = None
            if sys.platform == 'win32':
                for i, api in enumerate(host_apis):
                    if 'MME' in api['name']:
                        valid_api_index = i
                        break

            self.available_devices = []
            menu_items = []

            for i, dev in enumerate(devices):

                if dev['max_input_channels'] <= 0:
                    continue

                if valid_api_index is not None:
                    if dev['hostapi'] != valid_api_index:
                        continue

                dev_name = dev['name']
                self.available_devices.append((dev_name, i))

                display_name = dev_name[:25] + \
                    "..." if len(dev_name) > 25 else dev_name
                menu_items.append(f"{display_name}")

            if not menu_items:
                menu_items = ["Default Device"]
                self.available_devices = [(None, None)]

            self.device_menu['items'] = menu_items
            self.device_menu.set(0)

        except Exception as e:
            print(f"Error querying audio devices: {e}")
            self.device_menu['items'] = ["Error loading devices"]

    def on_device_selected(self, selection):
        """Callback when dropdown changes."""
        index_in_list = self.device_menu.selectedIndex
        if 0 <= index_in_list < len(self.available_devices):
            _, dev_id = self.available_devices[index_in_list]
            self.selected_device_index = dev_id

    def restart_speech_service(self):
        """
        Stops the current speech processor and starts a new one 
        with the selected device settings.
        """
        if self.speech_recognition_active:
            try:
                if self.speech_processor:
                    self.speech_processor.stop()
            except Exception as e:
                print(f"Error stopping speech: {e}")

            self.speech_recognition_active = False
            self.show_popup("Restarting Audio Service...")

            time.sleep(0.2)

        self.start_speech_recognition()

    def start_speech_recognition(self):
        """
        Starts the speech recognition service with the currently selected device index.
        """
        try:
            if not self.speech_processor:
                self.speech_processor = SpeechGloss(
                    callback=self.handle_speech_result,
                    device_index=self.selected_device_index
                )
            else:
                if hasattr(self.speech_processor, 'set_device'):
                    self.speech_processor.set_device(
                        self.selected_device_index)
                else:
                    self.speech_processor = SpeechGloss(
                        callback=self.handle_speech_result,
                        device_index=self.selected_device_index
                    )

            if self.speech_processor.start():
                self.speech_recognition_active = True

                device_label = "Default Device"
                if self.selected_device_index is not None:
                    found_name = None
                    for name, dev_id in self.available_devices:
                        if dev_id == self.selected_device_index:
                            found_name = name
                            break
                    if found_name:
                        device_label = found_name
                    else:
                        device_label = f"Device {self.selected_device_index}"

                self.show_popup(f"Listening on: {device_label}")
                self.speech_toggle_button['image'] = "assets/icons/speech-recognition-on.png"
            else:
                self.show_popup("Error: Speech failed to start")
        except Exception as e:
            self.gloss_text_node.setText(f"Error: {str(e)}")
            print(f"Speech Start Error: {e}")

    def toggle_speech_recognition(self):
        if not self.speech_recognition_active:
            self.start_speech_recognition()
        else:
            try:
                if self.speech_processor and self.speech_processor.stop():
                    self.speech_recognition_active = False
                    self.show_popup("Speech inactive.")
                    self.speech_toggle_button['image'] = "assets/icons/speech_recognition_off.png"
                else:
                    self.gloss_text_node.setText(
                        "Error: Failed to stop speech")
            except Exception as e:
                self.show_popup(f"Error: {str(e)}")

    def loadModels(self):
        """Load 3D character model, arms, and attach to scene graph."""
        try:
            body_path = self.get_panda_model_path('character/body.bam')
            print(f"Loading body from: {body_path}")
            self.torso = self.loader.loadModel(body_path)
            self.torso.reparentTo(self.render)
            self.torso.setPos(0, 0, -1.5)
            self.torso.setScale(0.7)
            self.torso.setHpr(0, 0, 0)

            rarm_path = self.get_panda_model_path('character/RArm.bam')
            print(f"Loading right arm from: {rarm_path}")
            self.rarm = self.loader.loadModel(rarm_path)
            self.rarm.reparentTo(self.torso)

            larm_path = self.get_panda_model_path('character/LArm.bam')
            print(f"Loading left arm from: {larm_path}")
            self.larm = self.loader.loadModel(larm_path)
            self.larm.reparentTo(self.torso)

            self.setup_arm_details()
            print("All models loaded successfully")

        except Exception as e:
            print(f"Error loading models: {e}")
            import traceback
            traceback.print_exc()
            raise

    def setup_arm_details(self):
        self.rthumb1 = self.rarm.find("**/t1")
        self.rthumb2 = self.rarm.find("**/t2")
        self.rindex1 = self.rarm.find("**/i1")
        self.rindex2 = self.rarm.find("**/i2")
        self.rindex3 = self.rarm.find("**/i3")
        self.rmiddle1 = self.rarm.find("**/m1")
        self.rmiddle2 = self.rarm.find("**/m2")
        self.rmiddle3 = self.rarm.find("**/m3")
        self.rring1 = self.rarm.find("**/r1")
        self.rring2 = self.rarm.find("**/r2")
        self.rring3 = self.rarm.find("**/r3")
        self.rpinky1 = self.rarm.find("**/p1")
        self.rpinky2 = self.rarm.find("**/p2")
        self.rpinky3 = self.rarm.find("**/p3")

        self.lthumb1 = self.larm.find("**/t1")
        self.lthumb2 = self.larm.find("**/t2")
        self.lindex1 = self.larm.find("**/i1")
        self.lindex2 = self.larm.find("**/i2")
        self.lindex3 = self.larm.find("**/i3")
        self.lmiddle1 = self.larm.find("**/m1")
        self.lmiddle2 = self.larm.find("**/m2")
        self.lmiddle3 = self.larm.find("**/m3")
        self.lring1 = self.larm.find("**/r1")
        self.lring2 = self.larm.find("**/r2")
        self.lring3 = self.larm.find("**/r3")
        self.lpinky1 = self.larm.find("**/p1")
        self.lpinky2 = self.larm.find("**/p2")
        self.lpinky3 = self.larm.find("**/p3")

    def setupLights(self):
        mainLight = DirectionalLight('main light')
        mainLight.setShadowCaster(True)
        mainLightNodePath = self.render.attachNewNode(mainLight)
        mainLightNodePath.setHpr(0, -40, 0)
        self.render.setLight(mainLightNodePath)
        ambientLight = AmbientLight('ambient light')
        ambientLight.setColor((0.2, 0.2, 0.2, 1))
        ambientLightNodePath = self.render.attachNewNode(ambientLight)
        self.render.setLight(ambientLightNodePath)
        self.render.setShaderAuto()

    def setupSkybox(self):
        try:
            skybox = self.loader.loadModel('skybox/skybox.bam')
            skybox.setScale(50)
            skybox.setBin('background', 1)
            skybox.setDepthWrite(0)
            skybox.setLightOff()
            skybox.reparentTo(self.render)
        except Exception as e:
            print(f"Could not load skybox: {e}")

    def get_resource_path(self, relative_path):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(base_path, relative_path)

    def get_panda_model_path(self, relative_path):
        return relative_path

    def loadAllPoseData(self):
        pose_file = self.get_resource_path("sign_poses.json")
        try:
            with open(pose_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Could not find sign_poses.json at {pose_file}")
            raise
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in sign_poses.json: {e}")
            raise

    def loadSignPoses(self, name):
        poses = self.gesture_data.get(name)
        pose = poses[0] if isinstance(poses, list) else poses
        if not pose:
            return
        l = pose["leftHand"]
        r = pose["rightHand"]

        self.larm.setPos(LVecBase3f(*l["pos"]))
        self.larm.setHpr(LVecBase3f(*l["hpr"]))
        self.rarm.setPos(LVecBase3f(*r["pos"]))
        self.rarm.setHpr(LVecBase3f(*r["hpr"]))

        def applyFingerPose(finger_parts, data):
            for part, pose_data in zip(finger_parts, data):
                part.setPos(*pose_data["pos"])
                part.setHpr(*pose_data["hpr"])

        if "fingers" in l:
            f = l["fingers"]
            if "thumb" in f:
                applyFingerPose([self.lthumb1, self.lthumb2], f["thumb"])
            if "index" in f:
                applyFingerPose([self.lindex1, self.lindex2,
                                 self.lindex3], f["index"])
            if "middle" in f:
                applyFingerPose([self.lmiddle1, self.lmiddle2,
                                 self.lmiddle3], f["middle"])
            if "ring" in f:
                applyFingerPose(
                    [self.lring1, self.lring2, self.lring3], f["ring"])
            if "pinky" in f:
                applyFingerPose([self.lpinky1, self.lpinky2,
                                 self.lpinky3], f["pinky"])

        if "fingers" in r:
            f = r["fingers"]
            if "thumb" in f:
                applyFingerPose([self.rthumb1, self.rthumb2], f["thumb"])
            if "index" in f:
                applyFingerPose([self.rindex1, self.rindex2,
                                 self.rindex3], f["index"])
            if "middle" in f:
                applyFingerPose([self.rmiddle1, self.rmiddle2,
                                 self.rmiddle3], f["middle"])
            if "ring" in f:
                applyFingerPose(
                    [self.rring1, self.rring2, self.rring3], f["ring"])
            if "pinky" in f:
                applyFingerPose([self.rpinky1, self.rpinky2,
                                 self.rpinky3], f["pinky"])

    def expandPoseSequence(self, sequence):
        result = []
        for word in sequence:
            if word.lower() in self.gesture_data:
                result.append(word.lower())
            else:
                for letter in word.lower():
                    if letter in self.gesture_data:
                        result.append(letter)
        return result

    def start_animation(self, text):
        self.stopAnimation()
        self.current_text = text.strip()
        words = self.current_text.split()
        self.expanded_sequence = self.expandPoseSequence(words)

        if not self.expanded_sequence:
            self.gloss_text_node.setText("No valid signs found in text")
            self.signing_complete = True
            return

        self.gloss_text_node.setText(f"Signing: {self.current_text}")
        self.pose_index = 0
        self.is_animating = True
        self.signing_complete = False
        if self.media_control_active and self.media_state == "playing":
            self.pause_media()
        self.taskMgr.add(self.animateNextPose, "SignAnimation")

    def stopAnimation(self):
        if self.is_animating:
            self.taskMgr.remove("SignAnimation")
            self.is_animating = False
            if hasattr(self, 'current_left_seq') and self.current_left_seq:
                self.current_left_seq.finish()
                self.current_left_seq = None
            if hasattr(self, 'current_right_seq') and self.current_right_seq:
                self.current_right_seq.finish()
                self.current_right_seq = None

    def slideArms(self):
        slide_distance = 0.5
        time = 0.2
        sequence = Sequence(
            LerpPosInterval(self.larm, time, self.larm.getPos()),
            LerpPosInterval(self.rarm, time, self.rarm.getPos() +
                            LVecBase3f(-slide_distance, 0, 0)),
            LerpPosInterval(self.larm, time, self.larm.getPos()),
            LerpPosInterval(self.rarm, time, self.rarm.getPos())
        )
        sequence.start()

    def animateNextPose(self, task):
        if self.pose_index >= len(self.expanded_sequence):
            if hasattr(self,
                       'current_left_seq') and self.current_left_seq and self.current_left_seq.isPlaying():
                return task.again
            if hasattr(self,
                       'current_right_seq') and self.current_right_seq and self.current_right_seq.isPlaying():
                return task.again

            self.loadSignPoses("default")
            self.pose_index = 0
            self.is_animating = False
            self.gloss_text_node.setText("Animation Complete")
            self.current_pose = ""

            self.signing_complete = True

            self.current_left_seq = None
            self.current_right_seq = None

            if self.media_control_active and self.media_state == "paused":
                self.resume_media()
            return Task.done

        pose_name = self.expanded_sequence[self.pose_index]

        if self.current_pose == pose_name and len(pose_name) == 1:
            self.slideArms()
            self.pose_index += 1
            return task.again

        self.current_pose = pose_name
        poses = self.gesture_data.get(pose_name)
        if not poses:
            self.pose_index += 1
            return task.again

        left_sequence = []
        right_sequence = []
        time = 0.005

        def addFingerLerp(hand_data, finger_map, sequence_list):
            if "fingers" not in hand_data:
                return
            for name, parts in finger_map.items():
                if name in hand_data["fingers"]:
                    for part, pose_data in zip(parts, hand_data["fingers"][name]):
                        sequence_list.append(LerpPosInterval(
                            part, 0.01, LVecBase3f(*pose_data["pos"])))
                        sequence_list.append(LerpHprInterval(
                            part, 0.01, LVecBase3f(*pose_data["hpr"])))

        def addHandAndFingers(pose):
            l = pose["leftHand"]
            r = pose["rightHand"]

            left_sequence.extend([
                LerpPosInterval(self.larm, time, LVecBase3f(*l["pos"])),
                LerpHprInterval(self.larm, time, LVecBase3f(*l["hpr"]))
            ])
            addFingerLerp(l, {
                "thumb": [self.lthumb1, self.lthumb2],
                "index": [self.lindex1, self.lindex2, self.lindex3],
                "middle": [self.lmiddle1, self.lmiddle2, self.lmiddle3],
                "ring": [self.lring1, self.lring2, self.lring3],
                "pinky": [self.lpinky1, self.lpinky2, self.lpinky3]
            }, left_sequence)

            right_sequence.extend([
                LerpPosInterval(self.rarm, time, LVecBase3f(*r["pos"])),
                LerpHprInterval(self.rarm, time, LVecBase3f(*r["hpr"]))
            ])
            addFingerLerp(r, {
                "thumb": [self.rthumb1, self.rthumb2],
                "index": [self.rindex1, self.rindex2, self.rindex3],
                "middle": [self.rmiddle1, self.rmiddle2, self.rmiddle3],
                "ring": [self.rring1, self.rring2, self.rring3],
                "pinky": [self.rpinky1, self.rpinky2, self.rpinky3]
            }, right_sequence)

        if isinstance(poses, list):
            for pose in poses:
                addHandAndFingers(pose)
        else:
            addHandAndFingers(poses)

        self.current_left_seq = None
        self.current_right_seq = None

        if left_sequence:
            self.current_left_seq = Sequence(*left_sequence)
            self.current_left_seq.start()

        if right_sequence:
            self.current_right_seq = Sequence(*right_sequence)
            self.current_right_seq.start()

        self.gloss_text_node.setText(f"Signing: {self.current_text}")
        self.recognized_text_node.setText(f"{pose_name.upper()}")

        task.delayTime = self.sign_delay
        self.pose_index += 1
        return task.again

    def show_popup(self, message, duration=1):
        if hasattr(self, "active_popup") and self.active_popup:
            self.active_popup.cleanup()
            self.active_popup = None

        popup = OnscreenText(
            text=message,
            pos=(0, -0.9),
            scale=0.05,
            fg=(1, 1, 1, 1),
            bg=(0, 0, 0, 0),
            align=TextNode.ACenter,
            parent=self.render2d
        )
        self.active_popup = popup

        def set_alpha(a):
            if popup.isEmpty():
                return
            popup.setColor(1, 1, 1, a)
            popup['bg'] = (0, 0, 0, 0)

        anim = Sequence(
            LerpFunc(set_alpha, fromData=0, toData=1, duration=0.25),
            Wait(duration),
            LerpFunc(set_alpha, fromData=1, toData=0, duration=0.25),
            Func(lambda: not popup.isEmpty() and popup.removeNode()),
            Func(setattr, self, "active_popup", None)
        )

        popup.cleanup = anim.finish
        anim.start()

    def setup_media_control(self):
        self.taskMgr.add(self.media_control_task, "MediaControlTask")

    def toggle_media_control(self):
        try:
            self.media_control_active = not self.media_control_active

            if self.media_control_active:
                self.show_popup("Media control starting (switch to media tab)")
                self.media_toggle_button['image'] = "assets/icons/media-control-on.png"
                self.last_media_action_time = time.time()
                self.media_state = "starting"
                print(
                    "Media control starting - switch to your media tab within 3 seconds!")
            else:
                self.show_popup("media control inactive")
                self.media_toggle_button['image'] = "assets/icons/media-control-off.png"
                self.media_state = "paused"
                print("Media control stopped")

        except Exception as e:
            print(f"Error toggling media control: {str(e)}")
            self.gloss_text_node.setText(f"Error: {str(e)}")

    def media_control_task(self, task):
        if not self.media_control_active:
            return Task.cont
        if not self.signing_complete:
            return Task.cont

        current_time = time.time()
        elapsed = current_time - self.last_media_action_time

        if self.media_state == "starting" and elapsed >= 3:
            self.last_media_action_time = current_time
            self.media_state = "playing"
            self.gloss_text_node.setText("Media playing")

        elif self.media_state == "playing" and elapsed >= self.play_interval:
            self.pause_media()

        return Task.cont

    def pause_media(self):
        self.simulate_space_press()
        self.last_media_action_time = time.time()
        self.media_state = "paused"
        self.gloss_text_node.setText("Media paused")

    def resume_media(self):
        self.simulate_space_press()
        self.last_media_action_time = time.time()
        self.media_state = "playing"
        self.gloss_text_node.setText("Media playing")

    def simulate_space_press(self):
        if sys.platform == 'win32':
            try:
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys(" ", 0)
            except ImportError:
                print(
                    "Could not import win32com.client - media control may not work properly")
        else:
            try:
                import pyautogui
                pyautogui.press('space')
            except ImportError:
                print("Could not import pyautogui - media control may not work properly")

    def reset_app(self):
        self.stopAnimation()
        try:
            self.loadSignPoses("default")
        except:
            pass

        self.recognized_text_node.setText("...")
        self.gloss_text_node.setText("Ready.")

        self.current_pose = "default"
        self.expanded_sequence = []
        self.pose_index = 0
        self.signing_complete = True

    def handle_speech_result(self, text, gloss):
        if text and gloss and not self.is_animating:
            self.recognized_text_node.setText(text)
            self.gloss_text_node.setText(gloss)
            self.start_animation(gloss)
