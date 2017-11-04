var getPubs = function(callback) {
    $.ajax({
      url: "https://api.github.com/repos/irishshagua/dublin-pubs-map/contents/postgres-pubs-dump.txt"
    }).then(function(data) {
      var decodedData = window.atob(data.content);
      var pubs = decodedData.split("\n").map(function(line) {
        var cols = line.split("\t")
        return {
          latitude: cols[0],
          longitude: cols[1],
          name: cols[2],
          description: cols[3]
        }
      })

      callback(pubs);
    });
}