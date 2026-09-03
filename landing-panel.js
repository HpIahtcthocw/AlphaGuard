/* Firebreak landing layer: live risk-gate demo + enter workspace */
(function(){
  var overlay=document.getElementById('ldOverlay');
  if(!overlay)return;

  function esc(s){var d=document.createElement('div');d.textContent=(s==null?'':s);return d.innerHTML;}
  function pct(v){if(v==null||isNaN(v))return '—';return (v*100).toFixed(2).replace(/^\s/,'')+'%';}

  // scenario switching
  var segBtns=[].slice.call(overlay.querySelectorAll('.ld-seg button'));
  var scenario='synthetic';
  segBtns.forEach(function(b){b.addEventListener('click',function(){
    scenario=b.getAttribute('data-scenario');
    segBtns.forEach(function(x){x.classList.remove('on','bad','good');if(x===b)x.classList.add('on',scenario==='proven'?'good':'bad');});
    runAudit();
  });});

  function runAudit(){
    var btn=overlay.querySelector('.ld-btn'),spin=overlay.querySelector('.ld-spin'),res=overlay.querySelector('.ld-result');
    var task=overlay.querySelector('.ld-task').value.trim();
    if(btn.disabled)return;btn.disabled=true;spin.style.display='block';res.style.display='none';
    fetch('/api/goai/audit-demo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:task,lang:'en',scenario:scenario})})
      .then(function(r){return r.ok?r.json():Promise.reject(new Error('HTTP '+r.status));})
      .then(function(d){
        res.style.display='flex';
        var blocked=d.verdict!=='ELIGIBLE';
        var checks=((d.evidence&&d.evidence.risk_gate)&&d.evidence.risk_gate.checks)||[];
        var gates='';
        checks.forEach(function(g){
          var pass=g.status!=='BLOCKED';
          gates+='<div class="ld-gate"><span class="ld-ico '+(pass?'pass':'block')+'">'+(pass?'✓':'✕')+'</span><b>'+esc(g.label)+'</b><span class="ld-st '+(pass?'pass':'block')+'">'+esc(g.status)+'</span></div>';
        });
        var verdict='<div class="ld-verdict '+(blocked?'blocked':'eligible')+'"><span class="ld-badge">'+(blocked?'BLOCKED':'ELIGIBLE')+'</span><span class="ld-t">'+esc(d.headline)+'</span></div>';
        var lock='<span class="ld-lock"><span class="ld-dot2'+(d.order_intent_created?'':' red')+'"></span>'+(d.order_intent_created?'ORDER INTENT WRITTEN':'ORDER INTENT — NOT CREATED')+'</span>';
        res.innerHTML=verdict+lock+'<div class="ld-gates">'+(gates||'<div class="ld-gate"><b>No gate records</b></div>')+'</div>';
        window.PIOApplyI18n?.(res);
      })
      .catch(function(e){
        res.style.display='flex';
        res.innerHTML='<div class="ld-verdict blocked"><span class="ld-badge">ERROR</span><span class="ld-t">'+esc(String(e))+'</span></div>';
        window.PIOApplyI18n?.(res);
      })
      .finally(function(){btn.disabled=false;spin.style.display='none';});
  }

  var runBtn=overlay.querySelector('.ld-btn');
  runBtn.addEventListener('click',runAudit);

  // enter workspace
  function enter(){
    overlay.addEventListener('transitionend',function(e){if(e.target===overlay)overlay.remove();});
    overlay.style.transition='opacity .28s ease,transform .28s ease';
    overlay.style.opacity='0';overlay.style.transform='translateY(-8px)';
  }
  [].slice.call(overlay.querySelectorAll('.ld-enter')).forEach(function(el){el.addEventListener('click',enter);});

  // auto-run once on first load
  setTimeout(runAudit,150);
})();