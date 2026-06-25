from kivy.app import App
from kivy.uix.widget import Widget


class EmptyRoot(Widget):
    pass


class DataToolsApp(App):
    title = "DataTools"

    def build(self):
        return EmptyRoot()
