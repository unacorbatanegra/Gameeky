import os

__dir__ = os.path.dirname(os.path.abspath(__file__))

from gi.repository import Gio, Gtk, Adw

from .scene import Scene as SceneView
from .grid import Grid as GridView
from .entity_row import EntityRow
from .scene_entity_window import SceneEntityWindow

from ..models.entity_row import EntityRow as EntityRowModel
from ..models.scene import Scene as SceneModel

from ...common.vector import Vector
from ...common.scanner import Description


@Gtk.Template(filename=os.path.join(__dir__, "scene_window.ui"))
class SceneWindow(Adw.ApplicationWindow):
    __gtype_name__ = "SceneWindow"

    aspect = Gtk.Template.Child()
    overlay = Gtk.Template.Child()
    adder = Gtk.Template.Child()
    eraser = Gtk.Template.Child()
    grid = Gtk.Template.Child()
    area = Gtk.Template.Child()
    time = Gtk.Template.Child()
    zoom_in = Gtk.Template.Child()
    zoom_out = Gtk.Template.Child()
    editor = Gtk.Template.Child()
    rotate = Gtk.Template.Child()
    spawner = Gtk.Template.Child()
    selection = Gtk.Template.Child()
    model = Gtk.Template.Child()
    factory = Gtk.Template.Child()

    def __init__(self, *args, **kargs) -> None:
        super().__init__(*args, **kargs)
        self._scene_model = SceneModel()

        self._scene_view = SceneView()
        self._grid_view = GridView()
        self._grid_view.connect("clicked", self.__on_clicked)

        self.overlay.props.child = self._scene_view
        self.overlay.add_overlay(self._grid_view)

        # XXX Move the UI file somehow
        self.time.connect("notify::selected-item", self.__on_time_changed)

        # XXX Move to the UI file somehow
        self._model = Gio.ListStore()
        self.model.props.model = self._model
        self.factory.connect("setup", self.__on_factory_setup)
        self.factory.connect("bind", self.__on_factory_bind)

    def __on_factory_setup(
        self,
        factory: Gtk.SignalListItemFactory,
        item: Gtk.ListItem,
    ) -> None:
        entity = EntityRow()
        item.set_child(entity)

    def __on_factory_bind(
        self,
        factory: Gtk.SignalListItemFactory,
        item: Gtk.ListItem,
    ) -> None:
        model = item.get_item()

        view = item.get_child()
        view.type_id = model.props.type_id
        view.name = model.props.name

    def __on_time_changed(self, *args) -> None:
        self._scene_model.time = float(self.time.props.selected)
        self._scene_model.refresh()

    def __on_clicked(self, grid: GridView, x: int, y: int) -> None:
        area = int(self.area.props.selected)

        if self.spawner.props.active is True:
            self._set_spawn_point(x, y)
            return

        if self.rotate.props.active is True:
            self._rotate_entity(x, y)
            return

        if self.editor.props.active is True:
            self._edit_entity(x, y)
            return

        if self.eraser.props.active is True:
            self._scene_model.remove(x, y, area)
            return

        if (item := self.selection.get_selected_item()) is None:
            return

        self._scene_model.add(item.props.type_id, x, y, None, area)

    def _set_spawn_point(self, x: int, y: int) -> None:
        entities = self._scene_model.find_all(x, y)
        depth = 0 if not entities else len(entities)
        position = Vector(x, y, z=depth)

        self._grid_view.highlight = position
        self._scene_model.spawn = position

    def _rotate_entity(self, x: int, y: int) -> None:
        entity = self._scene_model.find(x, y)

        if entity is None:
            return

        entity.rotate()

    def _edit_entity(self, x: int, y: int) -> None:
        entity = self._scene_model.find(x, y)

        if entity is None:
            return

        editor = SceneEntityWindow(
            entity=entity,
            model=self._scene_model,
            transient_for=self,
        )
        editor.present()

    def register(self, description: Description) -> None:
        self._model.append(
            EntityRowModel(
                type_id=description.id,
                name=description.game.default.name,
            )
        )

    def reset(self) -> None:
        self.adder.props.active = True
        self.grid.props.active = True
        self.area.props.selected = 0
        self.time.props.selected = 0

        # XXX Come on...
        for _ in list(self.model):
            self.model.remove(0)

    @Gtk.Template.Callback("on_zoom_in")
    def __on_zoom_in(self, *args) -> None:
        self._scene_view.scale += 1
        self._grid_view.scale += 1

    @Gtk.Template.Callback("on_zoom_out")
    def __on_zoom_out(self, *args) -> None:
        self._scene_view.scale -= 1
        self._grid_view.scale -= 1

    @Gtk.Template.Callback("on_grid_changed")
    def __on_grid_changed(self, button: Gtk.Button) -> None:
        self._grid_view.props.visible = button.props.active

    @Gtk.Template.Callback("on_entity_selected")
    def __on_entity_selected(self, *args) -> None:
        self.adder.props.active = True
        self.area.props.selected = 0

    @property
    def description(self) -> Description:
        return self._scene_model.description

    @description.setter
    def description(self, description: Description) -> None:
        self._scene_model.description = description

        self.aspect.props.ratio = self._scene_model.ratio

        self._grid_view.columns = self._scene_model.width
        self._grid_view.rows = self._scene_model.height
        self._grid_view.highlight = self._scene_model.spawn
        self._grid_view.scale = 1.0

        self._scene_view.model = self._scene_model
        self._scene_view.scale = 1.0
