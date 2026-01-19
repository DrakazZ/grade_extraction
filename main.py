import sys
import json
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

def load_config():
    '''Load configuration from config.json'''
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    '''Launch the application'''
    
    # Load config
    config = load_config()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Système d'Extraction de Notes")
    
    # Create and show main window
    window = MainWindow(config)
    window.show()
    
    # Run
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
