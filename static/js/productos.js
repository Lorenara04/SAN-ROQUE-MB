/**
 * LÓGICA DE INVENTARIO - LICORERA OLIMPO
 * Maneja búsqueda dinámica, escaneo de códigos y confirmaciones.
 */
document.addEventListener('DOMContentLoaded', function() {
    // Referencias a elementos del DOM (IDs actualizados del nuevo HTML)
    const globalInput = document.getElementById('global_search_input');
    const scannerInput = document.getElementById('codigo_scanner');
    const cantidadInput = document.getElementById('cantidad_scanner');
    const formScanner = scannerInput ? scannerInput.closest('form') : null;

    /**
     * Función Debounce: Retrasa la ejecución de la búsqueda para mejorar el rendimiento
     */
    function debounce(fn, wait) {
        let t;
        return function(...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        };
    }

    /**
     * Filtra las filas de la tabla de inventario basándose en el texto ingresado
     */
    function filterTable(query) {
        const q = (query || '').toLowerCase().trim();
        // Seleccionamos las filas de la tabla (usando la clase del nuevo diseño)
        const filas = document.querySelectorAll('.tabla-inventario tbody tr');
        
        filas.forEach(fila => {
            // Ignoramos la fila de "No hay productos" si existe
            if (fila.cells.length < 2) return;

            const text = fila.innerText.toLowerCase();
            const match = q === '' ? true : text.includes(q);
            
            // Mostrar u ocultar fila
            fila.style.display = match ? '' : 'none';

            // Resaltado visual de coincidencias (opcional, usa la clase .td-match del CSS)
            fila.querySelectorAll('td').forEach(td => {
                const tdText = td.innerText.toLowerCase();
                if (q !== '' && tdText.includes(q)) {
                    td.style.backgroundColor = 'rgba(184, 134, 11, 0.1)'; // Sutil dorado de fondo
                } else {
                    td.style.backgroundColor = '';
                }
            });
        });
    }

    // 1. Escuchador para el Buscador Global (Debounce de 250ms)
    if (globalInput) {
        globalInput.addEventListener('input', debounce(function(e) {
            filterTable(e.target.value);
        }, 250));
    }

    // 2. Lógica del Escáner / Recepción Rápida
    if (scannerInput) {
        // Al escanear (Enter), saltar al campo de cantidad o enviar si ya está listo
        scannerInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                const codigo = scannerInput.value.trim();
                
                if (codigo !== '') {
                    // Si el campo de cantidad está vacío o es 1, enviamos, 
                    // de lo contrario damos foco a cantidad para ajuste manual
                    if (cantidadInput && cantidadInput.value === "1") {
                        formScanner.submit();
                    } else {
                        cantidadInput.focus();
                    }
                }
            }
        });

        // Filtrar tabla mientras se escribe en el buscador de recepción rápida
        scannerInput.addEventListener('input', debounce(function(e) {
            filterTable(e.target.value);
        }, 150));
    }

    // 3. Gestión de Eliminación (Confirmación segura)
    // Buscamos los botones con la clase del nuevo diseño .btn-action-delete
    document.querySelectorAll('.btn-action-delete').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            // Si es un botón que no tiene href directo (porque es un link estilizado)
            if (!href) return; 

            e.preventDefault();
            
            // Intentamos obtener el nombre del producto desde el atributo del link o la fila
            const fila = this.closest('tr');
            const nombre = fila ? fila.querySelector('.fw-bold').innerText : "este artículo";

            // Usamos confirmación nativa para evitar dependencias externas
            const confirmacion = confirm(`⚠️ ALERTA DE SEGURIDAD\n\n¿Está seguro de eliminar "${nombre}" del inventario de Olimpo?\n\nEsta acción no se puede deshacer.`);
            
            if (confirmacion) {
                window.location.href = href;
            }
        });
    });
});