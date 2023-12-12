import os

from typing import Optional

from gi.repository import Gio, Gdk, Gtk, GObject, Adw

from .scene import Scene as SceneView
from .grid import Grid as GridView
from .entity_row import EntityRow
from .confirmation_window import ConfirmationWindow
from .scene_entity_popover import SceneEntityPopover
from .scene_entity_window import SceneEntityWindow
from .dropdown_helper import DropDownHelper

from ..models.area_row import AreaRow as AreaRowModel
from ..models.entity_row import EntityRow as EntityRowModel
from ..models.layer_row import LayerRow as LayerRowModel
from ..models.daytime_row import DayTimeRow as DayTimeRowModel
from ..models.scene import Scene as SceneModel
from ..definitions import Layer

from ...common.vector import Vector
from ...common.scanner import Description
from ...common.definitions import Format
from ...common.monitor import Monitor


@Gtk.Template(resource_path="/dev/tchx84/gameeky/editor/widgets/scene_window.ui")  # fmt: skip
class SceneWindow(Adw.ApplicationWindow):
    __gtype_name__ = "SceneWindow"

    __gsignals__ = {
        "reload": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    aspect = Gtk.Template.Child()
    overlay = Gtk.Template.Child()
    entities_view = Gtk.Template.Child()
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
    scene_page = Gtk.Template.Child()
    layer = Gtk.Template.Child()
    banner = Gtk.Template.Child()

    def __init__(self, *args, **kargs) -> None:
        super().__init__(*args, **kargs)
        self._scene_model = SceneModel()

        self._scene_view = SceneView()
        self._grid_view = GridView()
        self._grid_view.connect("clicked", self.__on_clicked)

        self.overlay.props.child = self._scene_view
        self.overlay.add_overlay(self._grid_view)

        self._popover = SceneEntityPopover(parent=self.entities_view)
        self._popover.connect("deleted", self.__on_entity_deleted)

        self._controller = Gtk.GestureClick()
        self._controller.set_button(Gdk.BUTTON_SECONDARY)
        self._controller.connect("pressed", self.__on_controller_pressed)
        self.entities_view.add_controller(self._controller)

        self._layer = DropDownHelper(self.layer, LayerRowModel)
        self._layer.index = Layer.MAX
        self._layer.connect("changed", self.__on_layer_changed)

        self._time = DropDownHelper(self.time, DayTimeRowModel, exclude=["dynamic"])
        self._time.index = 0
        self._time.connect("changed", self.__on_time_changed)

        self._area = DropDownHelper(self.area, AreaRowModel)
        self._area.index = 0

        # XXX Move to the UI file somehow
        self._model = Gio.ListStore()
        self.model.props.model = self._model
        self.factory.connect("setup", self.__on_factory_setup)
        self.factory.connect("bind", self.__on_factory_bind)

        self._monitor_ignored = False
        Monitor.default().connect("changed", self.__on_monitor_changed)

    def __on_entity_deleted(
        self, popover: SceneEntityPopover, row: EntityRowModel
    ) -> None:
        dialog = ConfirmationWindow(transient_for=self)
        dialog.connect("confirmed", self.__on_confirmed, row)
        dialog.present()

    def __on_confirmed(self, dialog: ConfirmationWindow, row: EntityRowModel) -> None:
        self._monitor_ignored = True

        os.remove(row.path)

        self._scene_model.remove_by_type_id(row.type_id)

        _, position = self._model.find(row)
        self._model.remove(position)

    def __on_controller_pressed(
        self,
        controller: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        if (widget := self.entities_view.pick(x, y, Gtk.PickFlags.DEFAULT)) is None:
            return

        row = widget.get_ancestor(EntityRow.__gtype__)

        self._popover.display(row, x, y)

    def __on_monitor_changed(self, monitor: Monitor) -> None:
        self.banner.props.revealed = not self._monitor_ignored
        self._monitor_ignored = False

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
        view.model = model

    def __on_time_changed(self, *args) -> None:
        self._scene_model.time = float(self._time.index)
        self._scene_model.refresh()

    def __on_layer_changed(self, *args) -> None:
        layer: Optional[int] = (
            self._layer.index if self._layer.index < Layer.MAX else None
        )

        self._scene_model.layer = layer
        self._scene_view.layer = layer

    def __on_clicked(self, grid: GridView, x: int, y: int) -> None:
        area = self._area.index

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
                path=description._path,
            )
        )

    def reset(self) -> None:
        self._scene_view.model = None
        self.overlay.props.visible = False

        self.adder.props.active = True
        self.grid.props.active = True
        self._area.index = 0
        self._time.index = 0
        self._layer.index = Layer.MAX

        self._model.remove_all()

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
        self._area.index = 0

    @Gtk.Template.Callback("on_reload_clicked")
    def __on_reload_clicked(self, *args) -> None:
        self.emit("reload")
        self.banner.props.revealed = False

    @property
    def suggested_name(self) -> str:
        return f"{self._scene_model.name.lower()}.{Format.SCENE}"

    @property
    def description(self) -> Description:
        return self._scene_model.description

    @description.setter
    def description(self, description: Description) -> None:
        self._scene_model.description = description

        self.overlay.props.visible = True
        self.aspect.props.ratio = self._scene_model.ratio

        self._grid_view.columns = self._scene_model.width
        self._grid_view.rows = self._scene_model.height
        self._grid_view.highlight = self._scene_model.spawn
        self._grid_view.scale = 1.0

        self._scene_view.model = self._scene_model
        self._scene_view.scale = 1.0

        self.scene_page.props.title = self._scene_model.name
