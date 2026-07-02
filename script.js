const ca = "GUdYAzh14TQcwUSBw79rnFJHZCv64fugTEsq1etDpump";

function copyCA() {
  navigator.clipboard.writeText(ca).then(() => {
    alert("Contract copied!");
  }).catch(() => {
    alert(ca);
  });
}

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) entry.target.classList.add("visible");
  });
}, { threshold: 0.12 });

document.querySelectorAll(".reveal").forEach(el => observer.observe(el));

document.addEventListener("mousemove", (e) => {
  const glow = document.querySelector(".cursor-glow");
  glow.style.left = `${e.clientX - 250}px`;
  glow.style.top = `${e.clientY - 250}px`;
});
