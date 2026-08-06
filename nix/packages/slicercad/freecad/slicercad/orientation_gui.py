"""FreeCAD task panel for inspecting and applying mechanical orientations."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

from . import cad_orientation, fem_result, orient, orientation_analysis

ApplyBuild = Callable[[Any, list[Any], orient.Vector3], Any]


def _vector_text(vector: orient.Vector3) -> str:
    return " ".join(f"{value:+.3f}" for value in vector)


def _compact_vector_text(vector: orient.Vector3) -> str:
    values = (0.0 if abs(value) < 5e-13 else value for value in vector)
    return "(" + ",".join(f"{value:.3g}" for value in values) + ")"


def _matrix_values(placement: Any) -> tuple[float, ...]:
    matrix = placement.toMatrix()
    return tuple(
        float(getattr(matrix, f"A{row}{column}"))
        for row in range(1, 5)
        for column in range(1, 5)
    )


def _property(obj: Any, property_type: str, name: str, description: str) -> None:
    if name not in getattr(obj, "PropertiesList", ()):
        obj.addProperty(property_type, name, "SlicerCAD", description)


def persist_analysis(
    document: Any,
    result: Any,
    part: Any,
    analysis: orientation_analysis.Analysis,
) -> Any:
    """Store the versioned plain-data record and its object references."""
    obj = document.getObject("SlicercadOrientationAnalysis")
    if obj is None:
        obj = document.addObject("App::FeaturePython", "SlicercadOrientationAnalysis")
        obj.Label = "Print orientation analysis"
    _property(obj, "App::PropertyLink", "FEMResult", "Solved FEM result used")
    _property(obj, "App::PropertyLink", "PrintableObject", "Ranked printable solid")
    _property(
        obj,
        "App::PropertyString",
        "AnalysisJSON",
        "Versioned load-aware orientation analysis",
    )
    _property(obj, "App::PropertyString", "MeshSignature", "Analysed mesh identity")
    _property(
        obj,
        "App::PropertyString",
        "Confidence",
        "Per-model convergence state",
    )
    obj.FEMResult = result
    obj.PrintableObject = part
    obj.AnalysisJSON = analysis.json()
    obj.MeshSignature = analysis.record["mesh_signature"]
    obj.Confidence = analysis.record["confidence"]
    document.recompute()
    return obj


class OrientationTaskPanel:
    """One-result mechanical ranking; convergence families come later."""

    def __init__(
        self,
        document: Any,
        results: list[Any],
        parts: list[Any],
        apply_build: ApplyBuild,
        *,
        current_build: orient.Vector3 = (0.0, 0.0, 1.0),
    ) -> None:
        self.document = document
        self.results = results
        self.parts = parts
        self.apply_build = apply_build
        self.current_build = current_build
        self.candidates: list[orient.Candidate] = []
        self.row_placements: dict[int, orient.CandidatePlacement] = {}
        self.analysis: orientation_analysis.Analysis | None = None
        self.analysis_object: Any | None = None
        self.highlight_scene: Any | None = None
        self.highlight_root: Any | None = None
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Analyze print orientations")
        self._build_form()
        self._populate_parts()

    def _build_form(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.form)
        selectors = QtWidgets.QFormLayout()
        self.result_combo = QtWidgets.QComboBox()
        self.part_combo = QtWidgets.QComboBox()
        for result in self.results:
            self.result_combo.addItem(str(result.Label))
        self.part_combo.currentIndexChanged.connect(self._load_face_candidates)
        self.result_combo.currentIndexChanged.connect(self._load_result_parts)
        selectors.addRow("FEM result", self.result_combo)
        selectors.addRow("Printable solid", self.part_combo)
        layout.addLayout(selectors)

        self.candidate_table = QtWidgets.QTableWidget(0, 4)
        self.candidate_table.setHorizontalHeaderLabels(
            ("Use", "Layer axis", "Source", "Face area (mm^2)")
        )
        self.candidate_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.candidate_table.itemChanged.connect(self._inputs_changed)
        self.candidate_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.candidate_table)

        add_row = QtWidgets.QGridLayout()
        self.user_components = []
        for column, (label, value) in enumerate((("X", 0.0), ("Y", 0.0), ("Z", 1.0))):
            add_row.addWidget(QtWidgets.QLabel(label), 0, column)
            component = QtWidgets.QDoubleSpinBox()
            component.setRange(-1.0, 1.0)
            component.setDecimals(4)
            component.setSingleStep(0.1)
            component.setValue(value)
            self.user_components.append(component)
            add_row.addWidget(component, 1, column)
        add_user = QtWidgets.QPushButton("Add direction")
        add_user.clicked.connect(self._add_user_candidate)
        add_row.addWidget(add_user, 2, 0, 1, 3)
        layout.addLayout(add_row)

        self.analyse_button = QtWidgets.QPushButton("Analyze")
        self.analyse_button.clicked.connect(self._analyse)
        layout.addWidget(self.analyse_button)

        self.result_table = QtWidgets.QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(
            (
                "ID",
                "Build",
                "Opening\n(MPa)",
                "Shear\n(MPa)",
                "Pareto",
            )
        )
        self.result_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.result_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.result_table.currentCellChanged.connect(self._selection_changed)
        result_header = self.result_table.horizontalHeader()
        for column in (0, 2, 3, 4):
            result_header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeToContents
            )
        result_header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.result_table)

        self.sensitivity = QtWidgets.QLabel("Orientation sensitivity: --")
        self.sensitivity.setWordWrap(True)
        self.selection_details = QtWidgets.QLabel("Selected orientation: --")
        self.selection_details.setWordWrap(True)
        self.relative = QtWidgets.QLabel("Compared with current: --")
        self.relative.setWordWrap(True)
        self.tie_state = QtWidgets.QLabel("Tie diagnosis: not checked")
        self.tie_state.setWordWrap(True)
        self.warning = QtWidgets.QLabel(orientation_analysis.COMPARATIVE_WARNING)
        self.warning.setWordWrap(True)
        layout.addWidget(self.sensitivity)
        layout.addWidget(self.selection_details)
        layout.addWidget(self.relative)
        layout.addWidget(self.tie_state)
        layout.addWidget(self.warning)

        highlight_row = QtWidgets.QHBoxLayout()
        highlight_row.addWidget(QtWidgets.QLabel("Critical tail"))
        self.highlight_mode = QtWidgets.QComboBox()
        self.highlight_mode.addItem("Opening", "opening")
        self.highlight_mode.addItem("Shear", "shear")
        self.highlight_mode.addItem("Hidden", None)
        self.highlight_mode.currentIndexChanged.connect(self._update_highlight)
        highlight_row.addWidget(self.highlight_mode)
        highlight_row.addStretch()
        layout.addLayout(highlight_row)

        actions = QtWidgets.QHBoxLayout()
        self.preview_button = QtWidgets.QPushButton("Preview")
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.send_button = QtWidgets.QPushButton("Send to slicer")
        self.preview_button.clicked.connect(self._preview)
        self.apply_button.clicked.connect(self._apply)
        self.send_button.clicked.connect(self._send)
        for button in (self.preview_button, self.apply_button, self.send_button):
            button.setEnabled(False)
            actions.addWidget(button)
        layout.addLayout(actions)

    def _load_face_candidates(self, _index: int = 0) -> None:
        if not self.parts:
            return
        part = self.parts[self.part_combo.currentIndex()]
        self.candidates = list(cad_orientation.face_candidates((part,)))
        self._invalidate_analysis()
        self._populate_candidates()

    def _load_result_parts(self, _index: int = 0) -> None:
        result = self.results[self.result_combo.currentIndex()]
        self.parts = cad_orientation.result_parts(self.document, result)
        self._populate_parts()

    def _populate_parts(self) -> None:
        self.part_combo.blockSignals(True)
        self.part_combo.clear()
        for part in self.parts:
            self.part_combo.addItem(str(part.Label))
        self.part_combo.blockSignals(False)
        self._load_face_candidates()

    def _populate_candidates(self) -> None:
        self.candidate_table.blockSignals(True)
        self.candidate_table.setRowCount(len(self.candidates))
        for row, candidate in enumerate(self.candidates):
            use = QtWidgets.QTableWidgetItem()
            use.setFlags(use.flags() | QtCore.Qt.ItemIsUserCheckable)
            use.setCheckState(QtCore.Qt.Checked)
            self.candidate_table.setItem(row, 0, use)
            self.candidate_table.setItem(
                row, 1, QtWidgets.QTableWidgetItem(_vector_text(candidate.build))
            )
            self.candidate_table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(candidate.source)
            )
            self.candidate_table.setItem(
                row, 3, QtWidgets.QTableWidgetItem(f"{candidate.area:.3f}")
            )
        self.candidate_table.resizeColumnsToContents()
        self.candidate_table.blockSignals(False)

    def _inputs_changed(self, _value: Any = None) -> None:
        self._invalidate_analysis()

    def _invalidate_analysis(self) -> None:
        self.analysis = None
        self.row_placements.clear()
        self.result_table.setRowCount(0)
        self.sensitivity.setText("Orientation sensitivity: --")
        self.selection_details.setText("Selected orientation: --")
        self.relative.setText("Compared with current: --")
        self.tie_state.setText("Tie diagnosis: not checked")
        self._clear_highlight()
        for button in (self.preview_button, self.apply_button, self.send_button):
            button.setEnabled(False)

    def _add_user_candidate(self) -> None:
        try:
            candidate = orient.Candidate(
                tuple(component.value() for component in self.user_components),
                source="user",
            )
        except ValueError as error:
            self._error(str(error))
            return
        limit = math.cos(math.radians(5.0))
        if any(
            abs(sum(a * b for a, b in zip(candidate.build, value.build, strict=True)))
            >= limit
            for value in self.candidates
        ):
            self._error("That direction duplicates an existing layer axis")
            return
        self.candidates.append(candidate)
        self._invalidate_analysis()
        self._populate_candidates()

    def _included_candidates(self) -> tuple[orient.Candidate, ...]:
        return tuple(
            candidate
            for row, candidate in enumerate(self.candidates)
            if self.candidate_table.item(row, 0).checkState() == QtCore.Qt.Checked
        )

    def _analyse(self) -> None:
        candidate_set = self._included_candidates()
        if not candidate_set:
            self._error("Select at least one orientation candidate")
            return
        result = self.results[self.result_combo.currentIndex()]
        part = self.parts[self.part_combo.currentIndex()]
        source_mesh = cad_orientation.source_mesh_for(self.document, result, part)
        if source_mesh is None:
            self._error(
                "The FEM result no longer has one matching source mesh for this solid"
            )
            return
        self.analyse_button.setEnabled(False)
        self.analyse_button.setText("Analyzing...")
        QtWidgets.QApplication.processEvents()
        try:
            field = fem_result.field_from_solved_result(
                result, mesh=source_mesh.FemMesh
            )
            self.analysis = orientation_analysis.analyse(
                result_object=str(result.Name),
                part_objects=(str(part.Name),),
                field=field,
                candidate_set=candidate_set,
                current_build=self.current_build,
            )
            self.analysis.record["coordinate_transform"] = {
                "from": "FEM result mesh",
                "to": "document coordinates",
                "matrix_row_major": (
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ),
            }
            self.analysis.record["part_placements"] = {
                str(part.Name): _matrix_values(part.Shape.Placement)
            }
            self.analysis.record["source_mesh_object"] = str(source_mesh.Name)
            self.analysis.record["environment"] = {
                "freecad_version": tuple(str(value) for value in FreeCAD.Version()),
                "mesh_generator": {
                    "name": str(getattr(source_mesh, "Tool", "unknown")),
                    "version": None,
                    "seed": None,
                },
                "solver": {"name": None, "version": None},
                "slicer": None,
            }
            self.analysis.record["candidate_coverage"] = {
                "available": len(self.candidates),
                "included": len(candidate_set),
                "excluded": len(self.candidates) - len(candidate_set),
            }
            self.analysis_object = persist_analysis(
                self.document, result, part, self.analysis
            )
            self._populate_results(candidate_set)
        except (AttributeError, KeyError, ValueError) as error:
            self._error(str(error))
        finally:
            self.analyse_button.setText("Analyze")
            self.analyse_button.setEnabled(True)

    def _populate_results(self, candidate_set: tuple[orient.Candidate, ...]) -> None:
        analysis = self.analysis
        if analysis is None:
            return
        ranking = analysis.ranking
        candidate_ids = {
            candidate: f"O{index + 1}" for index, candidate in enumerate(candidate_set)
        }
        self.row_placements.clear()
        rows = len(ranking.scores) * 2
        self.result_table.setRowCount(rows)
        row = 0
        for score in ranking.scores:
            candidate_id = candidate_ids[score.candidate]
            for placement in orient.candidate_placements((score.candidate,)):
                sign = "+" if placement.sign == 1 else "-"
                values = (
                    f"{candidate_id}{sign}",
                    _compact_vector_text(placement.build),
                    f"{score.value('opening', ranking.ranking_tail_fraction):.6g}",
                    f"{score.value('shear', ranking.ranking_tail_fraction):.6g}",
                    "yes" if score in ranking.pareto_front else "no",
                )
                for column, value in enumerate(values):
                    self.result_table.setItem(
                        row, column, QtWidgets.QTableWidgetItem(value)
                    )
                self.row_placements[row] = placement
                row += 1
        self.result_table.selectRow(0)
        sensitivity = next(
            value
            for value in ranking.orientation_sensitivity
            if value.tail_fraction == ranking.ranking_tail_fraction
        )
        ratio = (
            "not defined" if sensitivity.value is None else f"{sensitivity.value:.3f}"
        )
        self.sensitivity.setText(
            "Orientation sensitivity: "
            f"{ratio} ({sensitivity.numerator:.4g}/{sensitivity.denominator:.4g} MPa, "
            f"tail {100 * sensitivity.tail_fraction:g}%)"
        )
        self.tie_state.setText("Tie diagnosis: not checked (single FEM result)")
        for button in (self.preview_button, self.apply_button, self.send_button):
            button.setEnabled(True)
        self._selection_changed(0, 0, -1, -1)

    def _selected_placement(self) -> orient.CandidatePlacement | None:
        row = self.result_table.currentRow()
        return self.row_placements.get(row)

    def _preview(self) -> Any | None:
        placement = self._selected_placement()
        if placement is None:
            return None
        part = self.parts[self.part_combo.currentIndex()]
        return self.apply_build(self.document, [part], placement.build)

    def _apply(self) -> None:
        placement = self._selected_placement()
        if placement is None or self.analysis is None:
            return
        bed_placement = self._preview()
        self.analysis.record["selected_placement"] = {
            "build_direction": placement.build,
            "sign": placement.sign,
            "build_axis": placement.candidate.build,
            "source": placement.candidate.source,
            "bed_placement_matrix_row_major": _matrix_values(bed_placement),
        }
        if self.analysis_object is not None:
            self.analysis_object.AnalysisJSON = self.analysis.json()
            self.document.recompute()
        FreeCAD.Console.PrintMessage(
            f"SlicerCAD: applied print orientation {_vector_text(placement.build)}\n"
        )

    def _send(self) -> None:
        self._apply()
        FreeCADGui.runCommand("Slicercad_Send")

    def _error(self, message: str) -> None:
        FreeCAD.Console.PrintError(f"SlicerCAD: {message}\n")
        QtWidgets.QMessageBox.warning(self.form, "SlicerCAD", message)

    def _selection_changed(
        self, _row: int, _column: int, _previous_row: int, _previous_column: int
    ) -> None:
        analysis = self.analysis
        if analysis is None:
            return
        placement = self._selected_placement()
        if placement is None:
            return
        ranking = analysis.ranking
        score = next(
            value for value in ranking.scores if value.candidate == placement.candidate
        )
        fraction = ranking.ranking_tail_fraction

        def relative(channel: orient.Channel) -> str:
            current = analysis.current_score.value(channel, fraction)
            selected = score.value(channel, fraction)
            if current == 0.0:
                return "not defined"
            return f"{100 * (selected - current) / current:+.2f}%"

        self.relative.setText(
            "Compared with current: "
            f"opening {relative('opening')}, shear {relative('shear')}"
        )
        margins = {
            value.channel: value
            for value in ranking.margins
            if value.candidate_b == placement.candidate
            and value.scope == "adjacent"
            and value.tail_fraction == fraction
        }

        def margin(channel: orient.Channel) -> str:
            value = margins.get(channel)
            if value is None:
                return "--"
            return f"{value.signed_gap:+.4g} MPa ({100 * value.relative_gap:.2f}%)"

        self.selection_details.setText(
            f"Selected orientation: source {score.candidate.source}; "
            f"opening gap {margin('opening')}; shear gap {margin('shear')}; "
            "confidence not_checked"
        )
        diagnostics = [
            value
            for value in ranking.tie_diagnostics
            if placement.candidate in (value.candidate_a, value.candidate_b)
            and value.tail_fraction == fraction
        ]
        if diagnostics:
            details = ", ".join(
                f"{value.channel} overlap {value.critical_region_overlap:.3f}"
                for value in diagnostics
            )
            first = diagnostics[0]
            self.tie_state.setText(
                "Tie diagnosis: not checked (single FEM result); "
                f"{details}; tie band {100 * first.tie_band:g}%, "
                f"same-region threshold {first.same_region_overlap:.2f}"
            )
        else:
            self.tie_state.setText(
                "Tie diagnosis: not checked; no Pareto pair for this orientation"
            )
        self._update_highlight()

    def _clear_highlight(self) -> None:
        if self.highlight_scene is not None and self.highlight_root is not None:
            self.highlight_scene.removeChild(self.highlight_root)
        self.highlight_scene = None
        self.highlight_root = None

    def _update_highlight(self, _index: int = 0) -> None:
        self._clear_highlight()
        if self.analysis is None:
            return
        channel = self.highlight_mode.currentData()
        placement = self._selected_placement()
        if channel not in orient.CHANNELS or placement is None:
            return
        score = next(
            value
            for value in self.analysis.ranking.scores
            if value.candidate == placement.candidate
        )
        contributions = score.critical_samples(
            channel, self.analysis.ranking.ranking_tail_fraction
        )
        positions = [value.position for value in contributions if value.position]
        if not positions:
            return
        from pivy import coin

        gui_document = FreeCADGui.getDocument(self.document.Name)
        scene = gui_document.activeView().getSceneGraph()
        root = coin.SoSeparator()
        material = coin.SoMaterial()
        colour = (0.9, 0.15, 0.05) if channel == "opening" else (0.0, 0.65, 0.85)
        material.diffuseColor.setValue(*colour)
        material.emissiveColor.setValue(*colour)
        style = coin.SoDrawStyle()
        style.pointSize = 7.0
        coordinates = coin.SoCoordinate3()
        coordinates.point.setValues(0, len(positions), positions)
        points = coin.SoPointSet()
        points.numPoints = len(positions)
        for node in (material, style, coordinates, points):
            root.addChild(node)
        scene.addChild(root)
        self.highlight_scene = scene
        self.highlight_root = root

    def getStandardButtons(self) -> int:
        return int(QtWidgets.QDialogButtonBox.Close.value)

    def reject(self) -> None:
        self._clear_highlight()
        FreeCADGui.Control.closeDialog()
