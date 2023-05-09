
console.log("Script carregado com sucesso!");

document.addEventListener("DOMContentLoaded", function() {
  var uploadButton = document.querySelector("#upload-button");

  uploadButton.addEventListener("click", function(event) {
    event.preventDefault();

    console.log("Botão de upload clicado!");

  });
});