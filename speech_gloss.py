import json
import queue
import string
import sys, os
import threading
import time
import pyaudio
from nltk import pos_tag, WordNetLemmatizer
from nltk.corpus import stopwords, wordnet
from nltk.tokenize import word_tokenize
from vosk import Model, KaldiRecognizer


class SpeechGloss:
    """
    Continuously recognizes speech, converts it to sign language gloss,
    and passes results to a callback or queue.
    """

    def __init__(self, callback=None):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)
        model_path = os.path.join(base_path, "vosk-model-small-en-us-0.15")
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english')) - {
            'i', 'you', 'we', 'he', 'she', 'they', 'me', 'my', 'your', 'our', 'his', 'her', 'their'
        }
        self.gloss_map = {
            "i": "ME",
            "you": "YOU",
            "we": "US",
            "he": "HE",
            "she": "SHE",
            "they": "THEY",
            "am": "",
            "is": "",
            "'s": "",
            "'m": "",
            "n't": "",
            "'re": "",
            "'ve": "",
            "are": "",
            "was": "",
            "were": "",
            "going": "GO",
            "go": "GO",
            "had": "HAVE",
            "don't": "NOT",
            "not": "NOT",
            "no": "NOT",
            "won't": "NOT WILL",
            "store": "STORE",
            "because": "WHY",
            "milk": "MILK",
            "to": "",
            "the": "",
            "a": "",
            "an": "",
            "and": "PLUS",
            "but": "BUT",
            "this": "THIS",
            "that": "THAT",
            "there": "THERE",
            "here": "HERE",
            "what": "WHAT",
            "who": "WHO",
            "where": "WHERE",
            "when": "WHEN",
            "why": "WHY",
            "hello": "HI",
            "talk": "SPEAK",
            "learn": "LEARN",
            "try": "TRY",
            "coached": "COACH",
            "habits": "HABIT",
            "millions": "MILLION",
            "skills": "SKILL",
            "think": "OVERTHINKING"
        }

        self.model_path = model_path
        self.callback = callback
        self.running = False
        self.thread = None
        self.results = queue.Queue()

    def convert_to_sign_gloss(self, text):
        words = [w for w in word_tokenize(text.lower()) if w not in string.punctuation]
        pos_tags = pos_tag(words)

        def get_wordnet_pos(tag):
            if tag.startswith('J'):
                return wordnet.ADJ
            elif tag.startswith('V'):
                return wordnet.VERB
            elif tag.startswith('N'):
                return wordnet.NOUN
            elif tag.startswith('R'):
                return wordnet.ADV
            else:
                return wordnet.NOUN

        lemmatized_words = [self.lemmatizer.lemmatize(w, get_wordnet_pos(t)) for w, t in pos_tags]

        gloss_sequence = []
        seen_pronouns = set()
        for word in lemmatized_words:
            if word in self.stop_words and word not in self.gloss_map:
                continue
            gloss_word = self.gloss_map.get(word, word.upper()).strip()
            if not gloss_word:
                continue
            if gloss_word in {"ME", "YOU", "HE", "SHE", "US", "THEY"}:
                if gloss_word in seen_pronouns:
                    continue
                seen_pronouns.add(gloss_word)
            gloss_sequence.append(gloss_word)

        return " ".join(gloss_sequence)

    def start(self):
        """Start continuous speech recognition in a background thread"""
        if self.running:
            return False

        self.running = True
        self.thread = threading.Thread(target=self._listen_continuously)
        self.thread.daemon = True
        self.thread.start()
        return True

    def stop(self):
        """Stop background speech recognition"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        return True

    def get_latest_result(self):
        """Retrieve latest recognition result from internal queue (if no callback used)"""
        if not self.results.empty():
            return self.results.get()
        return None

    def _listen_continuously(self):
        """
        Constantly listens for speech, performs recognition and gloss conversion.
        Sends results via callback or internal queue.
        """
        try:
            model = Model(self.model_path)
            recognizer = KaldiRecognizer(model, 16000)
            mic = pyaudio.PyAudio()
            stream = mic.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8192
            )
            stream.start_stream()
            print("Continuous speech recognition started...")
            while self.running:
                data = stream.read(4096, exception_on_overflow=False)
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        gloss = self.convert_to_sign_gloss(text)
                        if self.callback:
                            self.callback(text, gloss)
                        else:
                            self.results.put((text, gloss))

                time.sleep(0.01)
            stream.stop_stream()
            stream.close()
            mic.terminate()
            print("Continuous speech recognition stopped.")
        except Exception as e:
            error_msg = f"Error in speech recognition: {str(e)}"
            print(error_msg)
            if self.callback:
                self.callback(error_msg, "")
            else:
                self.results.put((error_msg, ""))
            self.running = False
