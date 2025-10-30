const header = document.getElementById('main-header');
function toggleHeader() {
    if (window.scrollY > 50) {
        header.classList.add('hidden');
    } else {
        header.classList.remove('hidden');
    }
}
window.addEventListener('scroll', toggleHeader);
window.addEventListener('load', toggleHeader);
