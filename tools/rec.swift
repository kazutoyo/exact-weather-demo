// Records a USB-connected iPhone's screen (like QuickTime) to a .mov for N seconds.
// Usage: swift rec.swift <name substring> <seconds> <out.mov>
import AVFoundation
import CoreMediaIO

var prop = CMIOObjectPropertyAddress(
    mSelector: CMIOObjectPropertySelector(kCMIOHardwarePropertyAllowScreenCaptureDevices),
    mScope: CMIOObjectPropertyScope(kCMIOObjectPropertyScopeGlobal),
    mElement: CMIOObjectPropertyElement(kCMIOObjectPropertyElementMain))
var allow: UInt32 = 1
CMIOObjectSetPropertyData(CMIOObjectID(kCMIOObjectSystemObject), &prop, 0, nil, UInt32(MemoryLayout<UInt32>.size), &allow)

let args = CommandLine.arguments
let want = args[1], secs = Double(args[2])!, out = URL(fileURLWithPath: args[3])
var device: AVCaptureDevice?
for _ in 0..<50 {
    let found = AVCaptureDevice.DiscoverySession(deviceTypes: [.external], mediaType: .muxed, position: .unspecified).devices
        + AVCaptureDevice.DiscoverySession(deviceTypes: [.external], mediaType: .video, position: .unspecified).devices
    if let d = found.first(where: { $0.localizedName.contains(want) }) { device = d; break }
    RunLoop.current.run(until: Date().addingTimeInterval(0.2))
}
guard let device else { print("no device named \(want)"); exit(1) }
let session = AVCaptureSession()
session.addInput(try AVCaptureDeviceInput(device: device))
let file = AVCaptureMovieFileOutput()
session.addOutput(file)
class Done: NSObject, AVCaptureFileOutputRecordingDelegate {
    func fileOutput(_ o: AVCaptureFileOutput, didFinishRecordingTo u: URL, from c: [AVCaptureConnection], error: Error?) {
        print("saved", u.path, error.map { "\($0)" } ?? ""); exit(0)
    }
}
let done = Done()
session.startRunning()
RunLoop.current.run(until: Date().addingTimeInterval(1.5))
try? FileManager.default.removeItem(at: out)
file.startRecording(to: out, recordingDelegate: done)
print("recording", device.localizedName)
fflush(stdout)
RunLoop.current.run(until: Date().addingTimeInterval(secs))
file.stopRecording()
RunLoop.current.run(until: Date().addingTimeInterval(5))
