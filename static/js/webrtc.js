class WebRTCManager {
    constructor(socket, folder) {
        this.socket = socket;
        this.folder = folder;
        this.peerConnection = null;
        this.dataChannel = null;
        this.receiveBuffer = [];
        this.receivedSize = 0;
        this.fileToReceive = null;
        this.onFileReceived = null;
        this.onPeerFound = null;
        this.CHUNK_SIZE = 64 * 1024;
        this.peerId = null;
    }

    init() {
        this.socket.on('signal', (data) => {
            // Only process signals that are not from ourselves
            if (data.from !== this.socket.id) {
                this.handleSignal(data);
            }
        });

        this.socket.on('peer-found', (data) => {
            if (this.onPeerFound) {
                this.onPeerFound(data.sid);
            }
        });
    }

    findPeer() {
        this.socket.emit('find-peer', { folder: this.folder });
    }

    async handleSignal(data) {
        if (!this.peerConnection) {
            this.createPeerConnection(data.from);
        }

        if (data.signal.offer) {
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.signal.offer));
            const answer = await this.peerConnection.createAnswer();
            await this.peerConnection.setLocalDescription(answer);
            this.sendSignal({ answer: answer }, this.peerId);
        } else if (data.signal.answer) {
            await this.peerConnection.setRemoteDescription(new RTCSessionDescription(data.signal.answer));
        } else if (data.signal.candidate) {
            await this.peerConnection.addIceCandidate(new RTCIceCandidate(data.signal.candidate));
        }
    }

    createPeerConnection(peerId) {
        this.peerId = peerId;
        this.peerConnection = new RTCPeerConnection({
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        });

        this.peerConnection.onicecandidate = event => {
            if (event.candidate) {
                this.sendSignal({ candidate: event.candidate }, this.peerId);
            }
        };

        this.peerConnection.ondatachannel = event => {
            this.dataChannel = event.channel;
            this.setupDataChannelEvents();
        };
    }

    sendSignal(signal, to) {
        this.socket.emit('signal', {
            folder: this.folder,
            signal: signal,
            to: to,
            from: this.socket.id
        });
    }

    async sendFile(file, to) {
        if (!file || !to) return;
        this.createPeerConnection(to);
        this.dataChannel = this.peerConnection.createDataChannel('file-transfer');
        this.setupDataChannelEvents();

        const offer = await this.peerConnection.createOffer();
        await this.peerConnection.setLocalDescription(offer);
        this.sendSignal({ offer: offer }, to);

        this.dataChannel.onopen = () => {
            this.sendFileData(file);
        };
    }

    setupDataChannelEvents() {
        this.dataChannel.onmessage = (event) => {
            const data = event.data;
            if (typeof data === 'string') {
                this.fileToReceive = JSON.parse(data);
                this.receiveBuffer = [];
                this.receivedSize = 0;
            } else {
                this.receiveBuffer.push(data);
                this.receivedSize += data.byteLength;
                if (this.receivedSize === this.fileToReceive.size) {
                    const receivedFile = new File([new Blob(this.receiveBuffer)], this.fileToReceive.name, { type: this.fileToReceive.type });
                    if (this.onFileReceived) {
                        this.onFileReceived(receivedFile);
                    }
                    this.receiveBuffer = [];
                }
            }
        };
    }

    sendFileData(file) {
        this.dataChannel.send(JSON.stringify({ name: file.name, size: file.size, type: file.type }));
        let offset = 0;
        const reader = new FileReader();
        reader.onload = () => {
            this.dataChannel.send(reader.result);
            offset += reader.result.byteLength;
            if (offset < file.size) {
                readSlice(offset);
            }
        };
        const readSlice = o => {
            const slice = file.slice(o, o + this.CHUNK_SIZE);
            reader.readAsArrayBuffer(slice);
        };
        readSlice(0);
    }
}
