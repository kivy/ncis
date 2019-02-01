'''
Application example using build() + return
==========================================

An application can be built if you return a widget on build(), or if you set
self.root.
'''

import ncis
ncis.install()

import kivy

from kivy.app import App
from kivy.uix.button import Button
from kivy.lang import Builder

KV = '''
BoxLayout:
    Button:
    Button
    Button
    BoxLayout:
        Button
        Button
'''

class TestApp(App):

    def build(self):
        # return a Button() as a root widget
        return Builder.load_string(KV)


if __name__ == '__main__':
    TestApp().run()
