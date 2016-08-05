
var needed = [];
db.getCollection('works').find({}).forEach(function (item) {    
   item.repair_times.forEach(function (group, index) {
        group.groups.forEach(function (subgroup, subindex) {
            subgroup.works.forEach(function (work, workindex) {
                if (result = work.name.match(/- [A-Z]{2,5}/g)) {
                    needed.push({
                        _id: item._id,
                        result: result,
                        name: work.name,
                        indexes: '' + index + '-' + subindex + '-' + workindex
                    });
                }
            })
        });
   });
});
print(needed.length)
printjson(needed)
