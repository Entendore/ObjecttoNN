import sys
import numpy as np
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
    QHBoxLayout, QSplitter, QLabel, QSlider, QPushButton, 
    QLineEdit, QComboBox, QColorDialog, QGroupBox, QFormLayout,
    QToolBar, QCheckBox, QFileDialog, QStatusBar
)
from PySide6.QtCore import Qt, QTimer, QElapsedTimer
from PySide6.QtGui import QColor, QAction
import pyqtgraph as pg
import pyqtgraph.opengl as gl

pg.mkQApp("PySide6 Advanced 3D Visualizer")

STYLESHEET = """
    QMainWindow { background-color: #1e1e2e; }
    QTabWidget::pane { border: 1px solid #313244; background: #181825; }
    QTabBar::tab { background: #181825; color: #cdd6f4; padding: 8px 20px; border: 1px solid #313244; border-bottom: none; }
    QTabBar::tab:selected { background: #313244; border-bottom: 2px solid #89b4fa; }
    QWidget { color: #cdd6f4; background-color: transparent; }
    QGroupBox { border: 1px solid #313244; border-radius: 5px; margin-top: 1em; font-weight: bold; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
    QPushButton { background-color: #313244; border: 1px solid #45475a; padding: 6px; border-radius: 3px; }
    QPushButton:hover { background-color: #45475a; border: 1px solid #89b4fa; }
    QLineEdit { background-color: #313244; border: 1px solid #45475a; padding: 4px; border-radius: 2px; }
    QSlider::groove:horizontal { border: 1px solid #45475a; height: 4px; background: #181825; }
    QSlider::handle:horizontal { background: #89b4fa; width: 12px; margin: -5px 0; border-radius: 6px; }
    QCheckBox { spacing: 8px; }
    QToolBar { background: #181825; border-bottom: 1px solid #313244; spacing: 5px; padding: 3px; }
    QStatusBar { background: #181825; color: #a6adc8; }
"""


class MorphingShapeTab(QWidget):
    def __init__(self, status_bar):
        super().__init__()
        self.status_bar = status_bar
        
        splitter = QSplitter(Qt.Horizontal)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=5, elevation=25, azimuth=45)
        self.view.setBackgroundColor((24, 24, 37))
        splitter.addWidget(self.view)

        controls = self._create_controls()
        splitter.addWidget(controls)
        splitter.setSizes([700, 200])

        grid = gl.GLGridItem()
        grid.setSize(x=10, y=10)
        grid.setSpacing(x=1, y=1)
        grid.translate(0, 0, -1.5)
        self.view.addItem(grid)

        self.base_mesh = gl.MeshData.sphere(rows=40, cols=40)
        self.base_verts = self.base_mesh.vertexes()
        self.faces = self.base_mesh.faces()
        self.radii = np.sqrt(np.sum(self.base_verts**2, axis=1))
        self.unit_verts = self.base_verts / self.radii[:, np.newaxis]

        self.mesh_item = gl.GLMeshItem(
            vertexes=self.base_verts, faces=self.faces, 
            smooth=True, shader='shaded', drawEdges=False
        )
        self.color = QColor((50, 200, 230, 255))
        self._update_mesh_color()
        self.view.addItem(self.mesh_item)

        self.t = 0.0
        self.speed = 0.05
        self.amp = 0.2
        self.freq = 4.0
        self.auto_rotate = True

        self.is_playing = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_morph)
        self.timer.start(30)

    def _create_controls(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Shape Controls")
        form = QFormLayout(group)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(lambda v: setattr(self, 'speed', v / 100.0))
        form.addRow("Speed:", self.speed_slider)

        self.amp_slider = QSlider(Qt.Horizontal)
        self.amp_slider.setRange(0, 50)
        self.amp_slider.setValue(20)
        self.amp_slider.valueChanged.connect(lambda v: setattr(self, 'amp', v / 100.0))
        form.addRow("Amplitude:", self.amp_slider)

        self.freq_slider = QSlider(Qt.Horizontal)
        self.freq_slider.setRange(1, 10)
        self.freq_slider.setValue(4)
        self.freq_slider.valueChanged.connect(lambda v: setattr(self, 'freq', float(v)))
        form.addRow("Complexity:", self.freq_slider)

        self.shader_combo = QComboBox()
        self.shader_combo.addItems(["shaded", "balloon", "normalColor", "viewNormalColor"])
        self.shader_combo.currentIndexChanged.connect(self._update_shader)
        form.addRow("Shader:", self.shader_combo)

        self.rotate_check = QCheckBox("Auto Rotate Camera")
        self.rotate_check.setChecked(True)
        self.rotate_check.stateChanged.connect(lambda s: setattr(self, 'auto_rotate', bool(s)))
        form.addRow("", self.rotate_check)

        self.color_btn = QPushButton("Change Color")
        self.color_btn.clicked.connect(self._pick_color)
        form.addRow("", self.color_btn)

        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(lambda: self.view.setCameraPosition(distance=5, elevation=25, azimuth=45))
        form.addRow("", reset_btn)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _update_shader(self):
        self.mesh_item.setShader(self.shader_combo.currentText())

    def _pick_color(self):
        c = QColorDialog.getColor(self.color, self, "Select Shape Color")
        if c.isValid():
            self.color = c
            self._update_mesh_color()

    def _update_mesh_color(self):
        r, g, b, a = self.color.getRgbF()
        self.mesh_item.setColor((r, g, b, a))

    def update_morph(self):
        if not self.is_playing:
            return
            
        self.t += self.speed
        x, y, z = self.unit_verts[:, 0], self.unit_verts[:, 1], self.unit_verts[:, 2]

        morph_factor = (
            self.amp * np.sin(self.freq * x + self.t) +
            self.amp * np.cos(self.freq * y + self.t * 1.2) +
            self.amp * np.sin(self.freq * z + self.t * 0.8)
        )

        new_radii = self.radii + morph_factor
        new_verts = self.unit_verts * new_radii[:, np.newaxis]
        self.mesh_item.setMeshData(vertexes=new_verts, faces=self.faces, smooth=True)
        
        if self.auto_rotate:
            current_azimuth = self.view.cameraPosition()['azimuth']
            self.view.setCameraPosition(azimuth=current_azimuth + 0.2)


class NeuralNetworkTab(QWidget):
    def __init__(self, status_bar):
        super().__init__()
        self.status_bar = status_bar
        
        splitter = QSplitter(Qt.Horizontal)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.view = gl.GLViewWidget()
        self.view.setCameraPosition(distance=10, elevation=20, azimuth=45)
        self.view.setBackgroundColor((24, 24, 37))
        splitter.addWidget(self.view)

        controls = self._create_controls()
        splitter.addWidget(controls)
        splitter.setSizes([700, 200])

        grid = gl.GLGridItem()
        grid.setSize(x=12, y=12)
        grid.setSpacing(x=1, y=1)
        grid.translate(0, 0, -3)
        self.view.addItem(grid)

        self.layers = [4, 6, 6, 3]
        self.packets = []
        self.t = 0.0
        self.flow_speed = 0.05
        self.auto_spawn = False

        self.rebuild_network()

        self.is_playing = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_network)
        self.timer.start(30)

    def _create_controls(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Network Controls")
        form = QFormLayout(group)

        self.arch_input = QLineEdit("4, 6, 6, 3")
        form.addRow("Architecture:", self.arch_input)

        self.build_btn = QPushButton("Rebuild Network")
        self.build_btn.clicked.connect(self.rebuild_network)
        form.addRow("", self.build_btn)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 20)
        self.speed_slider.setValue(5)
        self.speed_slider.valueChanged.connect(lambda v: setattr(self, 'flow_speed', v / 100.0))
        form.addRow("Flow Speed:", self.speed_slider)

        self.spawn_btn = QPushButton("Inject Data Packet (Yellow)")
        self.spawn_btn.setStyleSheet("background-color: #4a4a00; border: 1px solid #f9e2af;")
        self.spawn_btn.clicked.connect(self.spawn_packet)
        form.addRow("", self.spawn_btn)

        self.auto_check = QCheckBox("Auto-spawn Forward Data")
        self.auto_check.stateChanged.connect(lambda s: setattr(self, 'auto_spawn', bool(s)))
        form.addRow("", self.auto_check)

        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(lambda: self.view.setCameraPosition(distance=10, elevation=20, azimuth=45))
        form.addRow("", reset_btn)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def rebuild_network(self):
        self.view.clear()
        grid = gl.GLGridItem()
        grid.setSize(x=12, y=12)
        grid.setSpacing(x=1, y=1)
        grid.translate(0, 0, -3)
        self.view.addItem(grid)

        try:
            text = self.arch_input.text()
            self.layers = [int(x.strip()) for x in text.split(',')]
            if len(self.layers) < 2 or any(l < 1 for l in self.layers):
                raise ValueError
        except ValueError:
            self.status_bar.showMessage("Invalid architecture. E.g: '4, 6, 3'")
            return

        self.generate_nodes()
        self.generate_edges()
        self.packets = []
        
        self.packet_scatter = gl.GLScatterPlotItem(pos=np.zeros((1,3)), color=(1, 1, 0, 1), size=10)
        self.view.addItem(self.packet_scatter)

    def generate_nodes(self):
        self.node_positions = []
        self.node_global_indices = {} 
        x_spacing = 3.0
        x_offset = -(len(self.layers) - 1) * x_spacing / 2.0
        
        flat_idx = 0
        for i, num_nodes in enumerate(self.layers):
            layer_nodes = []
            y_spacing = 1.5
            y_offset = -(num_nodes - 1) * y_spacing / 2.0
            
            for j in range(num_nodes):
                angle = (j / num_nodes) * np.pi * 2
                y = y_offset + j * y_spacing
                z = np.sin(angle) * 0.8
                x = x_offset + i * x_spacing
                layer_nodes.append([x, y, z])
                self.node_global_indices[(i, j)] = flat_idx
                flat_idx += 1
                
            self.node_positions.append(np.array(layer_nodes))
            
        all_nodes = np.vstack(self.node_positions)
        self.node_scatter = gl.GLScatterPlotItem(pos=all_nodes, color=(0.3, 0.4, 0.8, 1.0), size=15)
        self.view.addItem(self.node_scatter)
        
        self.node_activations = np.zeros(len(all_nodes))

    def generate_edges(self):
        self.edge_data = []
        edge_draw_list = []

        for i in range(len(self.layers) - 1):
            layer1 = self.node_positions[i]
            layer2 = self.node_positions[i+1]
            
            for idx1, n1 in enumerate(layer1):
                for idx2, n2 in enumerate(layer2):
                    t = np.linspace(0, 1, 20)
                    x = n1[0] + (n2[0] - n1[0]) * t
                    y = n1[1] + (n2[1] - n1[1]) * t
                    z = n1[2] + (n2[2] - n1[2]) * t
                    
                    vec = n2 - n1
                    perp = np.cross(vec, [0, 0, 1])
                    if np.linalg.norm(perp) < 0.01:
                        perp = np.cross(vec, [0, 1, 0])
                    perp = perp / np.linalg.norm(perp)
                    
                    wave_amp = 0.4 * np.sin(t * np.pi)
                    wave = np.sin(t * np.pi * 4) * wave_amp
                    y += perp[1] * wave
                    z += perp[2] * wave
                    
                    curve = np.vstack((x, y, z)).T
                    edge_draw_list.append(curve)
                    edge_draw_list.append(np.array([[np.nan, np.nan, np.nan]]))
                    
                    self.edge_data.append({
                        'curve': curve,
                        'from_layer': i,
                        'to_layer': i + 1,
                        'from_node_idx': idx1,
                        'to_node_idx': idx2
                    })
                    
        self.edge_draw_array = np.vstack(edge_draw_list)
        self.edge_item = gl.GLLinePlotItem(
            pos=self.edge_draw_array, color=(0.2, 0.8, 0.9, 0.4), width=2, mode='line_strip'
        )
        self.view.addItem(self.edge_item)

    def spawn_packet(self):
        start_layer = 0
        start_node_idx = np.random.randint(0, self.layers[0])
        possible_edges = [e for e in self.edge_data if e['from_layer'] == start_layer and e['from_node_idx'] == start_node_idx]
        color = (1.0, 0.9, 0.2, 1.0) # Yellow
            
        if not possible_edges:
            return
            
        chosen_edge = possible_edges[np.random.randint(0, len(possible_edges))]
        self.packets.append({
            'edge': chosen_edge,
            't': 0.0,
            'color': color
        })

    def update_network(self):
        if not self.is_playing:
            return
            
        self.t += 0.1
        
        if self.auto_spawn and np.random.rand() < 0.3:
            self.spawn_packet()
            
        # Decay node activations
        self.node_activations *= 0.95
        
        active_packets = []
        packet_positions = []
        packet_colors = []
        
        for p in self.packets:
            p['t'] += self.flow_speed
            
            curve = p['edge']['curve']
            idx_f = p['t'] * (len(curve) - 1)
            idx_i = int(np.floor(idx_f))
            idx_j = min(idx_i + 1, len(curve) - 1)
            frac = idx_f - idx_i
            
            if 0 <= idx_i < len(curve):
                pos = curve[idx_i] * (1 - frac) + curve[idx_j] * frac
                packet_positions.append(pos)
                packet_colors.append(p['color'])
            
            reached_end = p['t'] >= 1.0
            
            if reached_end:
                act_layer = p['edge']['to_layer']
                act_node = p['edge']['to_node_idx']
                
                g_idx = self.node_global_indices[(act_layer, act_node)]
                self.node_activations[g_idx] = 1.0 
                
                if act_layer < len(self.layers) - 1:
                    possible_edges = [e for e in self.edge_data if e['from_layer'] == act_layer and e['from_node_idx'] == act_node]
                    if possible_edges:
                        new_edge = possible_edges[np.random.randint(0, len(possible_edges))]
                        active_packets.append({'edge': new_edge, 't': 0.0, 'color': p['color']})
            else:
                active_packets.append(p)
        
        self.packets = active_packets
        
        if packet_positions:
            self.packet_scatter.setData(pos=np.array(packet_positions), color=np.array(packet_colors), size=10)
        else:
            self.packet_scatter.setData(pos=np.zeros((1,3)), size=0) 
            
        all_nodes = np.vstack(self.node_positions)
        r = 0.2 + 0.8 * self.node_activations
        g = 0.3 + 0.5 * self.node_activations
        b = 0.8 - 0.8 * self.node_activations
        a = np.ones_like(self.node_activations)
        colors = np.vstack((r, g, b, a)).T
        self.node_scatter.setData(color=colors)
        
        self.status_bar.showMessage(f"Active Packets: {len(self.packets)} | Layers: {len(self.layers)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 - Ultimate 3D Visualizer")
        self.resize(1000, 650)
        self.setStyleSheet(STYLESHEET)

        self.setStatusBar(self.statusBar())
        self.fps_label = QLabel("FPS: 0")
        self.statusBar().addPermanentWidget(self.fps_label)

        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        self.play_action = QAction("⏸ Pause", self)
        self.play_action.triggered.connect(self.toggle_play)
        toolbar.addAction(self.play_action)

        self.screenshot_action = QAction("📸 Screenshot", self)
        self.screenshot_action.triggered.connect(self.take_screenshot)
        toolbar.addAction(self.screenshot_action)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab1 = MorphingShapeTab(self.statusBar())
        self.tabs.addTab(self.tab1, "Morphing Shape")

        self.tab2 = NeuralNetworkTab(self.statusBar())
        self.tabs.addTab(self.tab2, "Neural Network (KAN)")

        self.frame_count = 0
        self.elapsed_timer = QElapsedTimer()
        self.elapsed_timer.start()
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)

    def toggle_play(self):
        if self.tab1.is_playing:
            self.tab1.is_playing = False
            self.tab2.is_playing = False
            self.play_action.setText("▶ Play")
        else:
            self.tab1.is_playing = True
            self.tab2.is_playing = True
            self.play_action.setText("⏸ Pause")

    def take_screenshot(self):
        current_tab = self.tabs.currentWidget()
        if hasattr(current_tab, 'view'):
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", "", "PNG Files (*.png)")
            if file_path:
                img = current_tab.view.grabFramebuffer()
                img.save(file_path)
                self.statusBar().showMessage(f"Screenshot saved to {file_path}", 3000)

    def update_fps(self):
        fps = 0
        if self.tab1.is_playing:
            fps = int(1000 / self.tab1.timer.interval())
        elif self.tab2.is_playing:
            fps = int(1000 / self.tab2.timer.interval())
        self.fps_label.setText(f"FPS: ~{fps}")


if __name__ == "__main__":
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())