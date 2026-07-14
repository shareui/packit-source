package de.robv.android.xposed;

import java.lang.reflect.Member;

// Compile-only stub of the exteraGram/LSPatch Xposed API. Not shipped in the
// dex — the real classes are provided by the host app at runtime.
public abstract class XC_MethodHook {
    public XC_MethodHook() {}
    public XC_MethodHook(int priority) {}

    protected void beforeHookedMethod(MethodHookParam param) throws Throwable {}
    protected void afterHookedMethod(MethodHookParam param) throws Throwable {}

    public static final class MethodHookParam {
        public Member method;
        public Object thisObject;
        public Object[] args;
        public Object getResult() { return null; }
        public void setResult(Object result) {}
        public Throwable getThrowable() { return null; }
        public boolean hasThrowable() { return false; }
        public void setThrowable(Throwable throwable) {}
    }

    public static class Unhook {
        public void unhook() {}
    }
}
