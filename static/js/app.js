/* Opti Cloud : confirmation avant d'ouvrir la page de suppression (comme le onclick="return confirm(...)" de l'original). */
document.addEventListener("click", function (event) {
    var link = event.target.closest("[data-confirm]");
    if (link && !window.confirm(link.getAttribute("data-confirm"))) {
        event.preventDefault();
    }
});
