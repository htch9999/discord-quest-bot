/** Animated counter */
(function(){
  function anim(el,target,dur){
    const s=performance.now();
    (function u(t){
      const p=Math.min((t-s)/dur,1);
      el.textContent=Math.round(target*(1-Math.pow(1-p,3))).toLocaleString();
      if(p<1)requestAnimationFrame(u)
    })(s)
  }
  
  window.counterInit=function(){
    const o=new IntersectionObserver(e=>{
      e.forEach(en=>{
        if(en.isIntersecting&&!en.target.dataset.counted){
          en.target.dataset.counted='1';
          const t=parseInt(en.target.dataset.countTo,10);
          if(!isNaN(t))anim(en.target,t,1200)
        }
      })
    },{threshold:0.5});
    document.querySelectorAll('[data-count-to]').forEach(el=>o.observe(el));
    window.triggerCounter = function() {
      document.querySelectorAll('[data-count-to]').forEach(el=>{
        const t=parseInt(el.dataset.countTo,10);
        if(isNaN(t)) return;
        
        // If the value has changed or it hasn't been counted yet, run animation
        const lastTarget = parseInt(el.dataset.lastTarget, 10);
        if (!el.dataset.counted || t !== lastTarget) {
          el.dataset.counted='1';
          el.dataset.lastTarget = t;
          anim(el,t,1200);
        }
      });
    };
  }
})();
