import os
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QTextBrowser, QListWidgetItem, QWidget, QDialog, QVBoxLayout, QToolBar, QPushButton, QAction, QFileDialog, QLabel, QSplitter, QLineEdit, QListWidget
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QMutex, QWaitCondition, QMutexLocker, QCoreApplication
from PyQt5.QtGui import QColor

class InterfazRI(QMainWindow):
    consulta_signal = pyqtSignal(str)  # Señal para enviar la consulta
    ventana_cerrada = pyqtSignal()  # Señal para cuando la ventana se cierre

    def __init__(self, sistema_ri):
        super().__init__()
        self.sistema_ri = sistema_ri
        self.initUI()

    def initUI(self):
        
        self.ventana_cerrada.connect(self.sistema_ri.terminar_programa)
        
        # Crear una instancia de QToolBar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Crear acciones para las opciones del menú
        abrir_action = QAction('Abrir', self)

        # Agregar acciones a la barra de herramientas
        toolbar.addAction(abrir_action)

        # Conectar las acciones a funciones
        abrir_action.triggered.connect(self.openDocument)

        # Widget de la consulta
        query_widget = QWidget()
        query_layout = QVBoxLayout()  # Usar QVBoxLayout para alinear en la parte superior izquierda
        query_label = QLabel("Consulta")
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Ingrese su consulta")

        # Botón para enviar la consulta
        send_button = QPushButton("Enviar")
        send_button.clicked.connect(self.enviar_consulta)
        
        # Botón para limpiar
        cls_button = QPushButton("Limpiar")
        cls_button.clicked.connect(self.limpiar)
        
        # Conectar la señal returnPressed del QLineEdit a una función
        self.text_input.returnPressed.connect(self.enviar_consulta)

        help_button = QPushButton("Ayuda para hacer la Consulta")
        help_button.clicked.connect(self.mostrar_ayuda)

        query_layout.addWidget(query_label)
        query_layout.addWidget(self.text_input)
        query_layout.addWidget(send_button)
        query_layout.addWidget(cls_button)
        query_layout.addWidget(help_button)
        query_widget.setLayout(query_layout)
        query_layout.addStretch(1)

        # Widget QListWidget para mostrar contenido posteriormente
        self.output_list = QListWidget()

        # Conectar señal itemClicked de output_list a la función update_document_displayed
        self.output_list.itemClicked.connect(self.update_document_displayed)
        
        # Dividir la mitad izquierda en dos partes, superior e inferior
        left_splitter = QSplitter()
        left_splitter.setOrientation(Qt.Vertical)
        left_splitter.addWidget(query_widget)
        left_splitter.addWidget(self.output_list)
        left_splitter.setSizes([200, 750])

        # Widget QTextBrowser para mostrar el contenido del documento
        self.text_browser = QTextBrowser()
        
        # Dividir la ventana en dos mitades, izquierda y derecha
        main_splitter = QSplitter()
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(self.text_browser)

        # Configurar el tamaño de las áreas
        main_splitter.setSizes([600, 600]) 
        # Configurar la ventana principal
        self.setCentralWidget(main_splitter)
        self.setGeometry(100, 100, 1200, 600)

        self.setWindowTitle('Sistema de RI Booleano')
        self.show()

    def openDocument(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly

        # Diálogo para seleccionar un archivo
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir Documento", "", "Archivos de Texto (*.txt);;Todos los Archivos (*)", options = options)

        if file_path:
            # Leer el contenido del archivo y mostrarlo en QTextBrowser
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.text_browser.setPlainText(content)
                file.close()

    def update_document_displayed(self, item):
        text_item = item.text()
        text_item_list = text_item.split(':')

        if "> Documento" in text_item:
            # Verificar si hay al menos tres partes (dos dos puntos)
            if len(text_item_list) >= 2:
                archivo = text_item_list[1].strip()
                directorio = self.sistema_ri.directorio

                working_dir = os.path.dirname(os.path.abspath(__file__))
                path = os.path.join(working_dir, directorio, archivo)

                with open(path, encoding="utf-8") as doc:
                    contenido = doc.read()
                    doc.close()
                    self.text_browser.setPlainText(contenido)
                    
    def enviar_consulta(self):
        consulta = self.text_input.text()
        # Envia la consulta al programa principal a través de la instancia
        # de SistemaRI que se pasó como argumento en el constructor
        self.consulta_signal.emit(consulta)

    def update_output(self, output):
        """
        Actualiza el output del programa
        """
        green = QColor(245, 245, 245)
        item = QListWidgetItem()
        item.setText(output)
        item.setBackground(green)  # Cambiar color del texto a verde
        self.output_list.addItem(item)

    def mostrar_ayuda(self):
        dialogo = QDialog(self)
        # Quítale la barra de título al diálogo
        dialogo.setWindowFlags(dialogo.windowFlags() | Qt.FramelessWindowHint)
        # Establece un estilo de borde personalizado
        dialogo.setStyleSheet("QDialog { border: 2px solid black; }")

        dialogo.setFixedSize(600, 300)
        layout = QVBoxLayout()

        mensaje = QLabel("Para ingresar a la consulta, se debe de ponerse en el cuadro de texto que se llama consulta.\nEn dicha consulta, cada elemento debe ir separado por un espacio, para que el programa pueda diferenciar cada uno de\nlos elementos, y así el programa lo pueda procesar sin problemas.\n\nEn la consulta, se debe de ingresar los operadores lógicos, los cuales son:\n\n"
                 "*AND (se usa con el carácter ’&’)*. Se utiliza para encontrar documentos que contienen todas las palabras clave.\n"
                 "*OR (se usa con el carácter ’|’)*. Se utiliza para encontrar documentos que contienen al menos una de las palabras clave.\n"
                 "*NOT (se usa con el carácter ’! ’)*. Se utiliza para excluir documentos que contienen una palabra clave específica.\n\n"
                 "Una vez terminada la consulta que se desee revisar, se procederá a darle al botón de ”Enviar” para identificar los \ndocumentos que cumplen con las condiciones.")
        ejemplo = QLabel("\nEjemplo de uso: (raices & secciones) | !(palabra)")
        layout.addWidget(mensaje)
        layout.addWidget(ejemplo)

        boton_cerrar = QPushButton('Cerrar', dialogo)
        boton_cerrar.clicked.connect(dialogo.close)
        layout.addWidget(boton_cerrar)

        dialogo.setLayout(layout)
        dialogo.exec_()

    def closeEvent(self, event):
        # Emitir la señal personalizada antes de cerrar la ventana
        self.ventana_cerrada.emit()
        super().closeEvent(event)  # Llamar al comportamiento predeterminado de cierre
        
    def salir(self):
        sys.exit()
        
    def limpiar(self):
        self.text_browser.setPlainText('')
        self.text_browser.setPlainText('')
        self.text_input.setText('')