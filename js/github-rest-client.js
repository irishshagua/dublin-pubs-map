var getPubs = function() {
    return $.ajax({
      url: "https://api.github.com/repos/irishshagua/dublin-pubs-map/contents/postgres-pubs-dump.txt"
    }).then(function(data) {
      var bytes = Uint8Array.from(window.atob(data.content), function(character) {
        return character.charCodeAt(0);
      });
      var decodedData = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      return decodedData.split(/\r?\n/).filter(function(line) {
        return line.trim() !== '';
      }).map(function(line) {
        var cols = line.split("\t");
        return {
          latitude: cols[0],
          longitude: cols[1],
          name: cols[2],
          description: cols[3]
        };
      });
    });
};