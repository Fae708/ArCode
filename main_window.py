import sys
import os
import subprocess
import tempfile
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTextEdit, QLabel, QSplitter
)
from PyQt6.QtGui import (
    QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QKeySequence, QShortcut
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression


# ─── Syntax Highlighter ───────────────────────────────────────────────────────

class CppHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#C792EA"))
        keyword_fmt.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "int", "float", "double", "char", "bool", "void", "long", "short",
            "unsigned", "signed", "const", "static", "return", "if", "else",
            "for", "while", "do", "switch", "case", "break", "continue",
            "class", "struct", "public", "private", "protected", "new", "delete",
            "include", "namespace", "using", "std", "true", "false", "nullptr",
            "auto", "template", "typename", "virtual", "override"
        ]
        for kw in keywords:
            self.rules.append((QRegularExpression(r'\b' + kw + r'\b'), keyword_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#C3E88D"))
        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_fmt))

        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#F78C6C"))
        self.rules.append((QRegularExpression(r'\b[0-9]+(\.[0-9]+)?\b'), num_fmt))

        pre_fmt = QTextCharFormat()
        pre_fmt.setForeground(QColor("#89DDFF"))
        self.rules.append((QRegularExpression(r'#\s*\w+'), pre_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#546E7A"))
        comment_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r'//[^\n]*'), comment_fmt))

        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#82AAFF"))
        self.rules.append((QRegularExpression(r'\b\w+(?=\s*\()'), func_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            match = pattern.globalMatch(text)
            while match.hasNext():
                m = match.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ─── Compiler Thread ──────────────────────────────────────────────────────────

class CompilerThread(QThread):
    output_ready = pyqtSignal(str, bool)

    def __init__(self, code, compiler_path):
        super().__init__()
        self.code = code
        self.compiler_path = compiler_path

    def run(self):
        with tempfile.NamedTemporaryFile(suffix=".cpp", delete=False, mode='w') as f:
            f.write(self.code)
            src_path = f.name

        out_path = src_path.replace(".cpp", ".exe" if os.name == "nt" else ".out")

        try:
            compile_result = subprocess.run(
                [self.compiler_path, src_path, "-o", out_path],
                capture_output=True, text=True, timeout=15
            )

            if compile_result.returncode != 0:
                self.output_ready.emit(compile_result.stderr, True)
                return

            run_result = subprocess.run(
                [out_path], capture_output=True, text=True, timeout=10
            )

            output = run_result.stdout
            if run_result.stderr:
                output += "\n" + run_result.stderr
            self.output_ready.emit(output if output else "(no output)", False)

        except subprocess.TimeoutExpired:
            self.output_ready.emit("Error: Program timed out (10s limit)", True)
        except Exception as e:
            self.output_ready.emit(f"Error: {str(e)}", True)
        finally:
            try:
                os.unlink(src_path)
                if os.path.exists(out_path):
                    os.unlink(out_path)
            except:
                pass


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.compiler_thread = None
        self.setup_compiler()
        self.init_ui()

    def setup_compiler(self):
        base = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base, "compiler", "g++.exe"),
            os.path.join(base, "compiler", "g++"),
            "g++",
        ]
        self.compiler_path = "g++"
        for c in candidates:
            if os.path.isfile(c):
                self.compiler_path = c
                break

    def init_ui(self):
        self.setWindowTitle("CppLearn")
        self.setMinimumSize(900, 620)
        self.resize(1100, 700)
        self.setStyleSheet("QMainWindow { background-color: #0D1117; }")

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Top Bar ──
        topbar = QWidget()
        topbar.setFixedHeight(48)
        topbar.setStyleSheet("background-color: #161B22; border-bottom: 1px solid #21262D;")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("CppLearn")
        title.setStyleSheet("color: #E6EDF3; font-size: 15px; font-weight: 700; font-family: 'Courier New'; letter-spacing: 1px;")

        self.status_label = QLabel("ready")
        self.status_label.setStyleSheet("color: #3FB950; font-size: 12px; font-family: 'Courier New';")

        self.run_btn = QPushButton("▶  Run")
        self.run_btn.setFixedSize(100, 32)
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636; color: #FFF;
                border: none; border-radius: 6px;
                font-size: 13px; font-weight: 600; font-family: 'Courier New';
            }
            QPushButton:hover { background-color: #2EA043; }
            QPushButton:pressed { background-color: #1A6E2A; }
            QPushButton:disabled { background-color: #21262D; color: #484F58; }
        """)
        self.run_btn.clicked.connect(self.run_code)

        self.clear_btn = QPushButton("✕  Clear")
        self.clear_btn.setFixedSize(90, 32)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8B949E;
                border: 1px solid #30363D; border-radius: 6px;
                font-size: 12px; font-family: 'Courier New';
            }
            QPushButton:hover { background-color: #21262D; color: #E6EDF3; }
        """)
        self.clear_btn.clicked.connect(self.clear_output)

        topbar_layout.addWidget(title)
        topbar_layout.addStretch()
        topbar_layout.addWidget(self.status_label)
        topbar_layout.addSpacing(16)
        topbar_layout.addWidget(self.clear_btn)
        topbar_layout.addSpacing(8)
        topbar_layout.addWidget(self.run_btn)
        root_layout.addWidget(topbar)

        # ── Splitter ──
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #21262D; height: 3px; }")

        # Editor
        editor_container = QWidget()
        editor_container.setStyleSheet("background-color: #0D1117;")
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        editor_label = QLabel("  main.cpp")
        editor_label.setFixedHeight(30)
        editor_label.setStyleSheet("color: #8B949E; font-size: 11px; font-family: 'Courier New'; background-color: #161B22; border-bottom: 1px solid #21262D; padding-left: 8px;")

        self.codeEditor = QTextEdit()
        self.codeEditor.setAcceptRichText(False)
        self.codeEditor.setTabStopDistance(32)
        self.codeEditor.setStyleSheet("""
            QTextEdit {
                background-color: #0D1117; color: #E6EDF3;
                border: none; font-family: 'Courier New'; font-size: 14px; padding: 16px;
                selection-background-color: #264F78;
            }
            QScrollBar:vertical { background: #161B22; width: 8px; border: none; }
            QScrollBar::handle:vertical { background: #30363D; border-radius: 4px; }
        """)
        self.highlighter = CppHighlighter(self.codeEditor.document())

        editor_layout.addWidget(editor_label)
        editor_layout.addWidget(self.codeEditor)

        # Output
        output_container = QWidget()
        output_container.setStyleSheet("background-color: #010409;")
        output_layout = QVBoxLayout(output_container)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        output_label = QLabel("  output")
        output_label.setFixedHeight(30)
        output_label.setStyleSheet("color: #8B949E; font-size: 11px; font-family: 'Courier New'; background-color: #161B22; border-bottom: 1px solid #21262D; border-top: 1px solid #21262D; padding-left: 8px;")

        self.outputBox = QTextEdit()
        self.outputBox.setReadOnly(True)
        self.outputBox.setStyleSheet("""
            QTextEdit {
                background-color: #010409; color: #3FB950;
                border: none; font-family: 'Courier New'; font-size: 13px; padding: 16px;
            }
            QScrollBar:vertical { background: #161B22; width: 8px; border: none; }
            QScrollBar::handle:vertical { background: #30363D; border-radius: 4px; }
        """)

        output_layout.addWidget(output_label)
        output_layout.addWidget(self.outputBox)

        splitter.addWidget(editor_container)
        splitter.addWidget(output_container)
        splitter.setSizes([460, 200])
        root_layout.addWidget(splitter)

        # ── Status Bar ──
        statusbar = QWidget()
        statusbar.setFixedHeight(24)
        statusbar.setStyleSheet("background-color: #238636;")
        statusbar_layout = QHBoxLayout(statusbar)
        statusbar_layout.setContentsMargins(12, 0, 12, 0)

        compiler_lbl = QLabel(f"compiler: {os.path.basename(self.compiler_path)}")
        compiler_lbl.setStyleSheet("color: #FFF; font-size: 10px; font-family: 'Courier New';")
        hint_lbl = QLabel("Ctrl+Enter to run")
        hint_lbl.setStyleSheet("color: #FFF; font-size: 10px; font-family: 'Courier New';")

        statusbar_layout.addWidget(compiler_lbl)
        statusbar_layout.addStretch()
        statusbar_layout.addWidget(hint_lbl)
        root_layout.addWidget(statusbar)

        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.run_code)

    def run_code(self):
        code = self.codeEditor.toPlainText().strip()
        if not code:
            return
        self.run_btn.setEnabled(False)
        self.run_btn.setText("⏳ Running")
        self.set_status("compiling...", "#F0B429")
        self.outputBox.setPlainText("")
        self.compiler_thread = CompilerThread(code, self.compiler_path)
        self.compiler_thread.output_ready.connect(self.on_output)
        self.compiler_thread.start()

    def on_output(self, text, is_error):
        color = "#FF6E6E" if is_error else "#3FB950"
        style = self.outputBox.styleSheet()
        for old in ["color: #3FB950", "color: #FF6E6E"]:
            style = style.replace(old, f"color: {color}")
        self.outputBox.setStyleSheet(style)
        self.outputBox.setPlainText(text)
        self.set_status("error" if is_error else "done", "#F85149" if is_error else "#3FB950")
        self.run_btn.setEnabled(True)
        self.run_btn.setText("▶  Run")

    def clear_output(self):
        self.outputBox.clear()
        self.set_status("ready", "#3FB950")

    def set_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-family: 'Courier New';")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
