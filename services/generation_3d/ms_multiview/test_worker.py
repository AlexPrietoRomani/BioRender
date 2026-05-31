"""
Archivo: test_worker.py
Fecha de modificación: 31/05/2026
Autor: Alex Prieto

Descripción:
Pruebas unitarias para validar las funciones del worker asíncrono de generación
multi-vista (MS 3.1).
"""

from PIL import Image
from worker import split_multiview_image


def test_split_multiview_image() -> None:
    """
    Verifica que la función split_multiview_image divide correctamente
    una imagen en grilla de 3x2 en 6 celdas independientes.
    """
    # Crear una imagen ficticia de 200x300
    grid_img = Image.new("RGB", (200, 300), color="white")
    views = split_multiview_image(grid_img)
    
    assert len(views) == 6
    for v in views:
        assert v.size == (100, 100)
    print("[+] Test unitario split_multiview_image paso exitosamente.")


if __name__ == "__main__":
    test_split_multiview_image()
