function singleItemPlaylist(fileUrl, name, basicAuth) {
    const hostUrl = `${window.location.protocol}//${basicAuth || ''}${window.location.host}`;
    const pd = [
        '#EXTM3U',
        `#EXTINF:0,${name}`,
        `${hostUrl}/${fileUrl}`
    ].join('\n');

    const blob = new Blob([pd], { endings: "native", type: "application/x-mpegURL" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `${name}.m3u`;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();

    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
}
