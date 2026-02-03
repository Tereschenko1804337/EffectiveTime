function copy_text(element){
    let innerText = element.previousElementSibling.innerText;
     navigator.clipboard.writeText(innerText);
     console.info('Текст скопирован!');
}