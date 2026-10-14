const mealForm = document.getElementById("mealForm");
const mealResults = document.getElementById("mealResults");

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, c => ({
        "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
    })[c]);
}
function imageFor(name) {
    const n = name.toLowerCase();
    let id = "photo-1512621776951-a57141f2eefd";
    if (n.includes("poha")) id = "photo-1606491956689-2ea866880c84";
    else if (n.includes("egg")) id = "photo-1525351484163-7529414344d8";
    else if (n.includes("chicken")) id = "photo-1532550907401-a500c9a57435";
    else if (n.includes("sandwich")) id = "photo-1528735602780-2552fd46c7af";
    else if (n.includes("fish")) id = "photo-1519708227418-c8fd9a32b7a2";
    else if (n.includes("paneer")) id = "photo-1567188040759-fb8a883dc6d8";
    else if (n.includes("dal")) id = "photo-1546833999-b9f581a1996d";
    else if (n.includes("chana")) id = "photo-1515543904379-3d757afe72e4";
    else if (n.includes("fruit")) id = "photo-1490474418585-ba9bad8fd0ea";
    return `https://images.unsplash.com/${id}?auto=format&fit=crop&w=700&q=80`;
}
if (mealForm && mealResults) {
    mealForm.addEventListener("submit", async event => {
        event.preventDefault();
        const payload = {
            foodType: document.getElementById("foodType").value,
            mealTime: document.getElementById("mealTime").value,
            goal: document.getElementById("goal").value,
            allergy: document.getElementById("allergy").value.trim()
        };
        mealResults.innerHTML = '<p class="text-muted-custom">Finding meal ideas...</p>';
        try {
            const response = await fetch("/api/recommendations", {
                method: "POST",
                headers: {"Content-Type":"application/json"},
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Could not generate suggestions.");
            if (!data.ideas.length) {
                mealResults.innerHTML = '<div class="card-dark p-3"><h3>No matching ideas found</h3><p class="text-muted-custom">Try changing your preferences or food exclusions. Always verify ingredients for allergies.</p></div>';
                return;
            }
            mealResults.innerHTML = `
              <div class="section-heading mb-3"><div><h2>Your Meal Ideas ✨</h2>
              <p class="text-muted-custom">Personalized rule-based suggestions</p></div>
              <span class="live-label">${data.ideas.length} IDEAS</span></div>
              <div class="row g-3">${data.ideas.map((meal,i)=>`
                <div class="col-12 col-sm-6">
                  <article class="card-dark food-preview">
                    <div class="food-preview-image">
                      <img src="${imageFor(meal.name)}" alt="${escapeHTML(meal.name)}" loading="lazy"
                           onerror="this.style.display='none'">
                      <span class="food-image-label">${String(i+1).padStart(2,"0")} · ${escapeHTML(payload.mealTime.toUpperCase())}</span>
                    </div>
                    <div class="food-preview-body">
                      <h3>${escapeHTML(meal.name)}</h3>
                      <p class="text-muted-custom">${escapeHTML(meal.description)}</p>
                      <span class="food-card-footer">Meal inspiration <span>↗</span></span>
                    </div>
                  </article>
                </div>`).join("")}</div>
              <div class="card-dark p-3 mt-3"><h3>💡 Helpful note</h3>
              <p class="text-muted-custom mb-0">${escapeHTML(data.note)}</p>
              <small class="text-muted-custom">These are rule-based ideas, not medical advice or a trained AI prediction.</small></div>`;
            mealResults.scrollIntoView({behavior:"smooth",block:"start"});
        } catch (error) {
            mealResults.innerHTML = `<div class="card-dark p-3"><p class="text-muted-custom">${escapeHTML(error.message)}</p></div>`;
        }
    });
}
